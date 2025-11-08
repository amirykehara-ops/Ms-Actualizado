import os
import json
import boto3
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Inicializamos clientes AWS
dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events')

# Tablas
customers_table = dynamodb.Table(os.environ.get('CUSTOMERS_TABLE', 'CustomersTable'))
orders_table = dynamodb.Table(os.environ.get('ORDERS_TABLE', 'OrdersTable'))
steps_table = dynamodb.Table(os.environ.get('STEPS_TABLE', 'StepsTable'))
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'PardosEventBus')


# ========================
# Función auxiliar: Convertir Decimal → float (recursiva)
# ========================
def convert_decimal(obj):
    """Convierte Decimal a float en dicts, listas y valores simples."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    if isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    return obj


# ========================
# Crear Pedido + Evento
# ========================
def create_order(event, context):
    try:
        body = json.loads(event.get('body', '{}'), parse_float=Decimal)
        order_id = f"o{int(datetime.utcnow().timestamp())}"
        pk = f"TENANT#pardos#ORDER#{order_id}"

        # Convertir TODOS los Decimal a float ANTES de guardar o publicar
        items_converted = [
            {
                "productId": item["productId"],
                "qty": item["qty"],
                "price": float(item["price"])
            }
            for item in body["items"]
        ]
        total_float = float(body["total"])

        # Guardar en DynamoDB (DynamoDB acepta Decimal, pero lo guardamos como float para consistencia)
        item = {
            "PK": pk,
            "SK": "INFO",
            "customerId": body["customerId"],
            "status": "CREATED",
            "items": items_converted,
            "total": total_float,
            "currentStep": "CREATED",
            "createdAt": datetime.utcnow().isoformat()
        }
        orders_table.put_item(Item=item)

        # Publicar evento (todo en float)
        event_detail = {
            "orderId": order_id,
            "customerId": body["customerId"],
            "total": total_float,
            "items": items_converted
        }
        eventbridge.put_events(Entries=[{
            'Source': 'pardos.orders',
            'DetailType': 'OrderCreated',
            'Detail': json.dumps(convert_decimal(event_detail)),  # Seguro con cualquier Decimal
            'EventBusName': EVENT_BUS_NAME
        }])

        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Order created successfully", "orderId": order_id})
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
# =====================================
# Obtener pedidos por cliente
# =====================================
def get_orders_by_customer(event, context):
    try:
        customer_id = event['pathParameters']['customerId']
        response = orders_table.scan(FilterExpression=Key('customerId').eq(customer_id))
        orders = response.get('Items', [])
        if not orders:
            return {"statusCode": 404, "body": json.dumps({"message": "No orders found"})}
        return {
            "statusCode": 200,
            "body": json.dumps({"orders": orders}, default=str)
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})})


# =====================================
# Cliente: GET / POST
# =====================================
def get_customer(event, context):
    try:
        customer_id = event['pathParameters']['customerId']
        pk = f"TENANT#pardos#CUSTOMER#{customer_id}"
        response = customers_table.get_item(Key={"PK": pk})
        if 'Item' not in response:
            return {"statusCode": 404, "body": json.dumps({"message": "Customer not found"})}
        return {"statusCode": 200, "body": json.dumps(response['Item'], default=str)}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

def create_customer(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        customer_id = body["customerId"]
        pk = f"TENANT#pardos#CUSTOMER#{customer_id}"
        item = {
            "PK": pk,
            "name": body["name"],
            "email": body["email"],
            "createdAt": datetime.utcnow().isoformat()
        }
        customers_table.put_item(Item=item)
        return {"statusCode": 201, "body": json.dumps({"message": "Customer created", "customerId": customer_id})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

# ========================
# Función auxiliar para actualizar paso
# ========================
def _start_step(order_id, step_name):
    pk = f"TENANT#pardos#ORDER#{order_id}"
    now = datetime.utcnow().isoformat()
    orders_table.update_item(
        Key={"PK": pk, "SK": "INFO"},
        UpdateExpression="SET currentStep = :step, #st = :status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":step": step_name, ":status": "IN_PROGRESS"}
    )
    steps_table.put_item(Item={
        "PK": pk,
        "SK": f"STEP#{step_name}#{now}",
        "stepName": step_name,
        "status": "IN_PROGRESS",
        "startedAt": now
    })
    eventbridge.put_events(Entries=[{
        'Source': 'pardos.orders',
        'DetailType': 'OrderStageStarted',
        'Detail': json.dumps({"orderId": order_id, "step": step_name}),
        'EventBusName': EVENT_BUS_NAME
    }])

# ========================
# Step Functions: COOKING
# ========================
def process_cooking(event, context):
    try:
        order_id = event['orderId']
        _start_step(order_id, "COOKING")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR:", str(e))
        raise

# ========================
# Step Functions: PACKAGING
# ========================
def process_packaging(event, context):
    try:
        order_id = event['orderId']
        _start_step(order_id, "PACKAGING")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR:", str(e))
        raise

# ========================
# Step Functions: DELIVERY
# ========================
def process_delivery(event, context):
    try:
        order_id = event['orderId']
        _start_step(order_id, "DELIVERY")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR:", str(e))
        raise

# ========================
# Step Functions: DELIVERED (final)
# ========================
def process_delivered(event, context):
    try:
        order_id = event['orderId']
        pk = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        orders_table.update_item(
            Key={"PK": pk, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "DELIVERED", ":status": "COMPLETED"}
        )
        steps_table.put_item(Item={
            "PK": pk,
            "SK": f"STEP#DELIVERED#{now}",
            "stepName": "DELIVERED",
            "status": "DONE",
            "startedAt": now,
            "finishedAt": now
        })
        eventbridge.put_events(Entries=[{
            'Source': 'pardos.orders',
            'DetailType': 'OrderDelivered',
            'Detail': json.dumps({"orderId": order_id}),
            'EventBusName': EVENT_BUS_NAME
        }])
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR:", str(e))
        raise
