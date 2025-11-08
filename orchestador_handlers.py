# orchestrator_handlers.py
import os
import json
import boto3
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
events = boto3.client('events')

ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'OrdersTable')
STEPS_TABLE = os.environ.get('STEPS_TABLE', 'StepsTable')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')

orders_table = dynamodb.Table(ORDERS_TABLE)
steps_table = dynamodb.Table(STEPS_TABLE)

def _put_step_record(order_id, step_name, status, started_at=None, finished_at=None):
    # SK incluye timestamp para mantener histórico
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    pk = f"TENANT#pardos#ORDER#{order_id}"
    sk = f"STEP#{step_name}#{ts}"
    item = {
        "PK": pk,
        "SK": sk,
        "stepName": step_name,
        "status": status,
        "startedAt": started_at or datetime.utcnow().isoformat(),
        "finishedAt": finished_at or None
    }
    steps_table.put_item(Item=item)
    return item

def _update_order_current_step(order_id, step_name, status):
    pk = f"TENANT#pardos#ORDER#{order_id}"
    # Actualizamos currentStep y status si corresponde
    update_expr = "SET currentStep = :cs"
    expr_vals = {":cs": step_name}
    if status == "DONE":
        update_expr += ", #s = :st"
        expr_vals[":st"] = "IN_PROGRESS" if step_name != "DELIVERED" else "DELIVERED"
    orders_table.update_item(
        Key={"PK": pk, "SK": "METADATA"},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=expr_vals
    )

def _publish_event(detail_type, detail):
    events.put_events(
        Entries=[
            {
                'Source': 'pf.pardosserverless.orchestrator',
                'DetailType': detail_type,
                'Detail': json.dumps(detail, default=str),
                'EventBusName': EVENT_BUS_NAME
            }
        ]
    )

# Lambda tarea: cocinar (COOKING)
def task_cooking(event, context):
    """
    Espera recibir: {"orderId": "...", "input": {...}}
    """
    order_id = event.get('orderId') or (event.get('input') or {}).get('orderId')
    if not order_id:
        return {"statusCode": 400, "message": "orderId required"}

    started_at = datetime.utcnow().isoformat()
    # Registra inicio
    _put_step_record(order_id, "COOKING", "IN_PROGRESS", started_at=started_at)
    _update_order_current_step(order_id, "COOKING", status="IN_PROGRESS")

    # --- Simula trabajo real (aquí iría lógica real) ---
    # Para demo: no sleep, solo marcamos como hecho inmediatamente
    finished_at = datetime.utcnow().isoformat()
    _put_step_record(order_id, "COOKING", "DONE", started_at=started_at, finished_at=finished_at)
    _update_order_current_step(order_id, "COOKING", status="DONE")

    # Publicamos eventos que Step Function o Dashboard/Notif consuman
    _publish_event("OrderStageCompleted", {"orderId": order_id, "stage": "COOKING", "finishedAt": finished_at})
    _publish_event("NotificationSent", {"orderId": order_id, "type": "STAGE_COMPLETED", "stage": "COOKING"})

    return {"status": "COOKING_DONE", "orderId": order_id}


# Lambda tarea: packaging (PACKAGING)
def task_packaging(event, context):
    order_id = event.get('orderId') or (event.get('input') or {}).get('orderId')
    if not order_id:
        return {"statusCode": 400, "message": "orderId required"}

    started_at = datetime.utcnow().isoformat()
    _put_step_record(order_id, "PACKAGING", "IN_PROGRESS", started_at=started_at)
    _update_order_current_step(order_id, "PACKAGING", status="IN_PROGRESS")

    finished_at = datetime.utcnow().isoformat()
    _put_step_record(order_id, "PACKAGING", "DONE", started_at=started_at, finished_at=finished_at)
    _update_order_current_step(order_id, "PACKAGING", status="DONE")

    _publish_event("OrderStageCompleted", {"orderId": order_id, "stage": "PACKAGING", "finishedAt": finished_at})
    _publish_event("NotificationSent", {"orderId": order_id, "type": "STAGE_COMPLETED", "stage": "PACKAGING"})

    return {"status": "PACKAGING_DONE", "orderId": order_id}


# Lambda tarea: delivery (DELIVERY)
def task_delivery(event, context):
    order_id = event.get('orderId') or (event.get('input') or {}).get('orderId')
    if not order_id:
        return {"statusCode": 400, "message": "orderId required"}

    started_at = datetime.utcnow().isoformat()
    _put_step_record(order_id, "DELIVERY", "IN_PROGRESS", started_at=started_at)
    _update_order_current_step(order_id, "DELIVERY", status="IN_PROGRESS")

    finished_at = datetime.utcnow().isoformat()
    _put_step_record(order_id, "DELIVERY", "DONE", started_at=started_at, finished_at=finished_at)
    # marcamos orden como DELIVERED en la tabla de órdenes
    pk = f"TENANT#pardos#ORDER#{order_id}"
    orders_table.update_item(
        Key={"PK": pk, "SK": "METADATA"},
        UpdateExpression="SET #s = :st, currentStep = :cs",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":st": "DELIVERED", ":cs": "DELIVERED"}
    )

    _publish_event("OrderStageCompleted", {"orderId": order_id, "stage": "DELIVERY", "finishedAt": finished_at})
    _publish_event("OrderDelivered", {"orderId": order_id, "deliveredAt": finished_at})
    _publish_event("NotificationSent", {"orderId": order_id, "type": "ORDER_DELIVERED"})

    return {"status": "DELIVERED", "orderId": order_id}
