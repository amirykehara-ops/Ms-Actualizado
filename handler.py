import os
import json
import boto3
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
# Inicializamos clientes AWS
dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events') # Nuevo: para publicar eventos
# Tablas
customers_table = dynamodb.Table(os.environ.get('CUSTOMERS_TABLE', 'CustomersTable'))
orders_table = dynamodb.Table(os.environ.get('ORDERS_TABLE', 'OrdersTable'))
steps_table = dynamodb.Table(os.environ.get('STEPS_TABLE', 'StepsTable')) # Nueva tabla para steps
# Nombre del EventBus (debe coincidir con serverless.yml)
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'PardosEventBus')
# ========================
# 🧾 Crear un nuevo pedido
# ========================
from decimal import Decimal
import json

def create_order(event, context):
    try:
        # Parsear body con Decimal
        body = json.loads(event.get('body', '{}'), parse_float=Decimal)

        # Validaciones básicas
        customer_id = body.get("customerId")
        items_raw = body.get("items", [])
        total_decimal = body.get("total")

        if not customer_id or not items_raw or total_decimal is None:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields"})}

        order_id = f"o{int(datetime.utcnow().timestamp())}"
        pk = f"TENANT#pardos#ORDER#{order_id}"

        # === GUARDAR EN DYNAMODB: Usar Decimal ===
        items_for_dynamo = [
            {
                "productId": item["productId"],
                "qty": int(item["qty"]),
                "price": Decimal(str(item["price"]))  # ← Decimal para DynamoDB
            }
            for item in items_raw
        ]

        item = {
            "PK": pk,
            "SK": "INFO",
            "customerId": customer_id,
            "status": "CREATED",
            "items": items_for_dynamo,
            "total": Decimal(str(total_decimal)),  # ← Decimal para DynamoDB
            "currentStep": "CREATED",
            "createdAt": datetime.utcnow().isoformat()
        }
        orders_table.put_item(Item=item)

        # === EVENTBRIDGE: Usar float para JSON ===
        items_for_event = [
            {
                "productId": item["productId"],
                "qty": item["qty"],
                "price": float(item["price"])  # ← float para JSON
            }
            for item in items_raw
        ]

        eventbridge.put_events(Entries=[{
            'Source': 'pardos.orders',
            'DetailType': 'OrderCreated',
            'Detail': json.dumps({
                "orderId": order_id,
                "customerId": customer_id,
                "total": float(total_decimal),  # ← float
                "items": items_for_event
            }),
            'EventBusName': EVENT_BUS_NAME
        }])

        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Order created", "orderId": order_id})
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
# =====================================
# 👤 Obtener información del cliente
# =====================================
def get_customer(event, context):
    try:
        customer_id = event['pathParameters']['customerId']
        pk = f"TENANT#pardos#CUSTOMER#{customer_id}"
        response = customers_table.get_item(Key={"PK": pk})
        if 'Item' not in response:
            return {"statusCode": 404, "body": json.dumps({"message": "Customer not found"})}
        return {
            "statusCode": 200,
            "body": json.dumps(response['Item'], default=str)
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
# ==========================
# 👤 Crear un nuevo cliente
# ==========================
def create_customer(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        customer_id = body["customerId"]
        pk = f"TENANT#pardos#CUSTOMER#{customer_id}"
        item = {
            "PK": pk,
            "name": body["name"], # Corregido: Quité SK ya que la tabla solo tiene PK (HASH)
            "email": body["email"],
            "createdAt": datetime.utcnow().isoformat()
        }
        customers_table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Customer created successfully", "customerId": customer_id})
        }
    except Exception as e:
        print("ERROR:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
# Nuevas Lambdas para Step Functions (una por paso, simple: actualiza estado y registra step)
# Procesar COOKING
# ========================
# Función auxiliar: Iniciar un paso
# ========================
def _start_step(order_id, step_name):
    pk = f"TENANT#pardos#ORDER#{order_id}"
    now = datetime.utcnow().isoformat()
    
    # Actualizar OrdersTable
    orders_table.update_item(
        Key={"PK": pk, "SK": "INFO"},
        UpdateExpression="SET currentStep = :step, #st = :status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":step": step_name, ":status": "IN_PROGRESS"}
    )
    
    # Registrar en StepsTable
    steps_table.put_item(Item={
        "PK": pk,
        "SK": f"STEP#{step_name}#{now}",
        "stepName": step_name,
        "status": "IN_PROGRESS",
        "startedAt": now
    })
    
    # Publicar evento
    eventbridge.put_events(Entries=[{
        'Source': 'pardos.orders',
        'DetailType': 'OrderStageStarted',
        'Detail': json.dumps({"orderId": order_id, "step": step_name}),
        'EventBusName': EVENT_BUS_NAME
    }])


# ========================
# COOKING
# ========================
def process_cooking(event, context):
    try:
        order_id = event['detail']['orderId']  # ← CORREGIDO
        _start_step(order_id, "COOKING")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR in process_cooking:", str(e))
        raise


# ========================
# PACKAGING
# ========================
def process_packaging(event, context):
    try:
        order_id = event['detail']['orderId']  # ← CORREGIDO
        _start_step(order_id, "PACKAGING")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR in process_packaging:", str(e))
        raise


# ========================
# DELIVERY
# ========================
def process_delivery(event, context):
    try:
        order_id = event['detail']['orderId']  # ← CORREGIDO
        _start_step(order_id, "DELIVERY")
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR in process_delivery:", str(e))
        raise


# ========================
# DELIVERED (FINAL)
# ========================
def process_delivered(event, context):
    try:
        order_id = event['detail']['orderId']  # ← CORREGIDO
        pk = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        
        # Finalizar orden
        orders_table.update_item(
            Key={"PK": pk, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "DELIVERED", ":status": "COMPLETED"}
        )
        
        # Registrar paso final
        steps_table.put_item(Item={
            "PK": pk,
            "SK": f"STEP#DELIVERED#{now}",
            "stepName": "DELIVERED",
            "status": "DONE",
            "startedAt": now,
            "finishedAt": now
        })
        
        # Evento final
        eventbridge.put_events(Entries=[{
            'Source': 'pardos.orders',
            'DetailType': 'OrderDelivered',
            'Detail': json.dumps({"orderId": order_id}),
            'EventBusName': EVENT_BUS_NAME
        }])
        
        return {"orderId": order_id}
    except Exception as e:
        print("ERROR in process_delivered:", str(e))
        raise
