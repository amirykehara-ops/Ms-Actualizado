# Pardos Chicken - Pedidos Serverless  
**Microservicio 100% Serverless con EventBridge + Step Functions + DynamoDB**

Flujo automático al crear un pedido:  
**`COOKING → PACKAGING → DELIVERY → DELIVERED`**

---

## Endpoints (HTTP API)

| Método | Ruta | Descripción |
|--------|------|-----------|
| `POST` | `/customers` | Crear cliente |
| `GET`  | `/customers/{customerId}` | Ver cliente |
| `POST` | `/orders` | Crear pedido → dispara Step Functions |
| `GET`  | `/orders/{customerId}` | Listar pedidos del cliente |
| `GET`  | `/order/{orderId}` | Ver pedido + cliente + progreso |

---

## Arquitectura

```text
POST /orders 
  → DynamoDB (OrdersTable) 
  → EventBridge (OrderCreated) 
  → Step Functions (OrderWorkflow)
     ├── process_cooking
     ├── process_packaging
     ├── process_delivery
     └── process_delivered → DynamoDB (StepsTable)

Prueba Rápida (cURL)
bash# 1. Crear cliente
curl -X POST https://2wmcf9zj7e.execute-api.us-east-1.amazonaws.com/customers \
  -H "Content-Type: application/json" \
  -d '{
    "customerId": "c100",
    "name": "Ana López",
    "email": "ana@utec.edu.pe"
  }'

# 2. Crear pedido
curl -X POST https://2wmcf9zj7e.execute-api.us-east-1.amazonaws.com/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customerId": "c100",
    "items": [
      {"productId": "pollo_1_4", "qty": 1, "price": 25.9},
      {"productId": "chicha", "qty": 1, "price": 8.5}
    ],
    "total": 34.4
  }'

# → Respuesta: {"message": "Order created", "orderId": "o1738795678"}

# 3. Esperar 15 segundos (flujo automático)

# 4. Ver pedido completo
curl https://2wmcf9zj7e.execute-api.us-east-1.amazonaws.com/order/o1738795678
Salida esperada:
json{
  "orderId": "o1738795678",
  "status": "COMPLETED",
  "currentStep": "DELIVERED",
  "total": 34.4,
  "customer": {"name": "Ana López"},
  "steps": ["COOKING", "PACKAGING", "DELIVERY", "DELIVERED"]
}

Verificación
Step Functions

AWS Console → Step Functions
Buscar: OrderWorkflow
Ver ejecución → 4 pasos en verde

DynamoDB (CLI)
bash# OrdersTable
aws dynamodb get-item \
  --table-name OrdersTable \
  --key '{"PK": {"S": "TENANT#pardos#ORDER#o1738795678"}, "SK": {"S": "INFO"}}' \
  --region us-east-1

# StepsTable (4 pasos)
aws dynamodb query \
  --table-name StepsTable \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TENANT#pardos#ORDER#o1738795678"}}' \
  --region us-east-1

Despliegue
bashnpm install -g serverless
sls deploy --stage dev

Estructura del Proyecto
text.
├── handler.py       ← Lógica de todas las Lambdas
├── serverless.yml   ← Infraestructura como código
└── README.md        ← Este archivo

Recursos AWS Creados








































ServicioNombreFunciónDynamoDBCustomersTableClientesDynamoDBOrdersTablePedidosDynamoDBStepsTableHistorial de pasosEventBridgePardosEventBusEventosStep FunctionsOrderWorkflowOrquestaciónIAM RoleLabRolePermisos

Notas Técnicas

status → palabra reservada → usar #st en UpdateExpression
Decimal → convertir a float solo para EventBridge
GET /order/{id} → evita conflicto con /orders/{customerId}
ScanIndexForward=True → ordena por SK


Tecnologías

Python 3.13
AWS Lambda
API Gateway (HTTP API)
DynamoDB
EventBridge
Step Functions
Serverless Framework
