entonces dame el codigo actualizado:
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
def create_order(event, context):
    try:
        body = json.loads(event.get('body', '{}'), parse_float=Decimal)
        order_id = f"o{int(datetime.utcnow().timestamp())}"
        pk = f"TENANT#pardos#ORDER#{order_id}"

        # Convertir TODOS los Decimal a float ANTES de guardar/event
        items = [
            {
                "productId": item["productId"],
                "qty": item["qty"],
                "price": float(item["price"])  # ← Conversión aquí
            }
            for item in body["items"]
        ]
        total = float(body["total"])  # ← Conversión aquí

        item = {
            "PK": pk,
            "SK": "INFO",
            "customerId": body["customerId"],
            "status": "CREATED",
            "items": items,  # ← Ya convertidos
            "total": total,
            "currentStep": "CREATED",
            "createdAt": datetime.utcnow().isoformat()
        }
        orders_table.put_item(Item=item)

        # Publicar evento (todo float)
        eventbridge.put_events(Entries=[{
            'Source': 'pardos.orders',
            'DetailType': 'OrderCreated',
            'Detail': json.dumps({
                "orderId": order_id,
                "customerId": body["customerId"],
                "total": total,
                "items": items
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
# 🔍 Obtener pedidos por ID de cliente
# =====================================
def get_orders_by_customer(event, context):
    try:
        customer_id = event['pathParameters']['customerId']
        # Buscar todos los pedidos que correspondan al customerId
        response = orders_table.scan(
            FilterExpression=Key('customerId').eq(customer_id)
        )
        orders = response.get('Items', [])
        if not orders:
            return {"statusCode": 404, "body": json.dumps({"message": "No orders found for this customer"})}
        return {
            "statusCode": 200,
            "body": json.dumps({"orders": orders}, default=str)
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
def process_cooking(event, context):
    try:
        order_id = event['orderId']
        pk_order = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        # Actualizar OrdersTable
        orders_table.update_item(
            Key={"PK": pk_order, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "COOKING", ":status": "IN_PROGRESS"}
        )
        # Registrar en StepsTable
        pk_step = pk_order
        sk_step = f"STEP#COOKING#{now}"
        steps_table.put_item(Item={
            "PK": pk_step,
            "SK": sk_step,
            "stepName": "COOKING",
            "status": "IN_PROGRESS",
            "startedAt": now
        })
        # Publicar evento completado (opcional, para notificaciones futuras)
        eventbridge.put_events(
            Entries=[{
                'Source': 'pardos.orders',
                'DetailType': 'OrderStageStarted',
                'Detail': json.dumps({"orderId": order_id, "step": "COOKING"}),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        return {"orderId": order_id, "step": "COOKING"} # Paso a siguiente en Step Functions
    except Exception as e:
        print("ERROR:", str(e))
        raise e # Fallar el task si error
# Procesar PACKAGING (similar)
def process_packaging(event, context):
    try:
        order_id = event['orderId']
        pk_order = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        # Actualizar OrdersTable
        orders_table.update_item(
            Key={"PK": pk_order, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "PACKAGING", ":status": "IN_PROGRESS"}
        )
        # Registrar en StepsTable
        pk_step = pk_order
        sk_step = f"STEP#PACKAGING#{now}"
        steps_table.put_item(Item={
            "PK": pk_step,
            "SK": sk_step,
            "stepName": "PACKAGING",
            "status": "IN_PROGRESS",
            "startedAt": now
        })
        eventbridge.put_events(
            Entries=[{
                'Source': 'pardos.orders',
                'DetailType': 'OrderStageStarted',
                'Detail': json.dumps({"orderId": order_id, "step": "PACKAGING"}),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        return {"orderId": order_id, "step": "PACKAGING"}
    except Exception as e:
        print("ERROR:", str(e))
        raise e
# Procesar DELIVERY
def process_delivery(event, context):
    try:
        order_id = event['orderId']
        pk_order = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        orders_table.update_item(
            Key={"PK": pk_order, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "DELIVERY", ":status": "IN_PROGRESS"}
        )
        pk_step = pk_order
        sk_step = f"STEP#DELIVERY#{now}"
        steps_table.put_item(Item={
            "PK": pk_step,
            "SK": sk_step,
            "stepName": "DELIVERY",
            "status": "IN_PROGRESS",
            "startedAt": now
        })
        eventbridge.put_events(
            Entries=[{
                'Source': 'pardos.orders',
                'DetailType': 'OrderStageStarted',
                'Detail': json.dumps({"orderId": order_id, "step": "DELIVERY"}),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        return {"orderId": order_id, "step": "DELIVERY"}
    except Exception as e:
        print("ERROR:", str(e))
        raise e
# Procesar DELIVERED (final)
def process_delivered(event, context):
    try:
        order_id = event['orderId']
        pk_order = f"TENANT#pardos#ORDER#{order_id}"
        now = datetime.utcnow().isoformat()
        orders_table.update_item(
            Key={"PK": pk_order, "SK": "INFO"},
            UpdateExpression="SET currentStep = :step, status = :status",
            ExpressionAttributeValues={":step": "DELIVERED", ":status": "COMPLETED"}
        )
        pk_step = pk_order
        sk_step = f"STEP#DELIVERED#{now}"
        steps_table.put_item(Item={
            "PK": pk_step,
            "SK": sk_step,
            "stepName": "DELIVERED",
            "status": "DONE",
            "startedAt": now,
            "finishedAt": now
        })
        eventbridge.put_events(
            Entries=[{
                'Source': 'pardos.orders',
                'DetailType': 'OrderDelivered',
                'Detail': json.dumps({"orderId": order_id}),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        return {"orderId": order_id, "step": "DELIVERED"}
    except Exception as e:
        print("ERROR:", str(e))
        raise e
