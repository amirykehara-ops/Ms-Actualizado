# handler.py
import os
import json
import boto3
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Inicializamos recursos
dynamodb = boto3.resource('dynamodb')
events = boto3.client('events')  # EventBridge client

CUSTOMERS_TABLE = os.environ.get('CUSTOMERS_TABLE', 'CustomersTable')
ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'OrdersTable')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')  # puede ser 'default' o tu EventBusName

customers_table = dynamodb.Table(CUSTOMERS_TABLE)
orders_table = dynamodb.Table(ORDERS_TABLE)

# ========================
# 🧾 Crear un nuevo pedido
# ========================
def create_order(event, context):
    try:
        # Convierte floats a Decimal para DynamoDB
        body = json.loads(event.get('body', '{}'), parse_float=Decimal)

        # Validaciones básicas
        if "customerId" not in body or "items" not in body or "total" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "customerId, items y total son obligatorios"})}

        # Generamos un ID único para el pedido
        order_id = f"o{int(datetime.utcnow().timestamp())}"
        pk = f"TENANT#pardos#ORDER#{order_id}"

        # Construimos el ítem a guardar
        item = {
            "PK": pk,
            "SK": "METADATA",
            "customerId": body["customerId"],
            "status": "CREATED",
            "items": body["items"],
            "total": Decimal(str(body["total"])),
            "currentStep": "CREATED",
            "createdAt": datetime.utcnow().isoformat()
        }

        # Guardamos en DynamoDB
        orders_table.put_item(Item=item)

        # Publicamos evento en EventBridge para que arranque el Step Function (vía regla)
        event_detail = {
            "eventType": "OrderCreated",
            "orderId": order_id,
            "tenant": "pardos",
            "customerId": body["customerId"],
            "total": float(body["total"]),
            "items": body["items"],
            "createdAt": item["createdAt"]
        }

        response = events.put_events(
            Entries=[
                {
                    'Source': 'pf.pardosserverless',
                    'DetailType': 'OrderCreated',
                    'Detail': json.dumps(event_detail, default=str),
                    'EventBusName': EVENT_BUS_NAME
                }
            ]
        )

        # Verificamos si EventBridge aceptó el evento
        failed_count = response.get('FailedEntryCount', 0)
        if failed_count > 0:
            print("WARNING: some events failed to put:", response)

        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Order created successfully", "orderId": order_id})
        }

    except Exception as e:
        print("ERROR create_order:", str(e))
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

        # Convertimos Decimals a tipos JSON serializables
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError

        return {
            "statusCode": 200,
            "body": json.dumps({"orders": orders}, default=decimal_default)
        }

    except Exception as e:
        print("ERROR get_orders_by_customer:", str(e))
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
        print("ERROR get_customer:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# ==========================
# 👤 Crear un nuevo cliente
# ==========================
def create_customer(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        if "customerId" not in body or "name" not in body or "email" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "customerId, name y email son obligatorios"})}

        customer_id = body["customerId"]
        pk = f"TENANT#pardos#CUSTOMER#{customer_id}"
        item = {
            "PK": pk,
            "SK": "INFO",
            "name": body["name"],
            "email": body["email"],
            "phone": body.get("phone", ""),
            "address": body.get("address", ""),
            "createdAt": datetime.utcnow().isoformat()
        }

        customers_table.put_item(Item=item)

        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Customer created successfully", "customerId": customer_id})
        }

    except Exception as e:
        print("ERROR create_customer:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
