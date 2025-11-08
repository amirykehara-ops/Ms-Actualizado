# Ms-Actualizado
Pardos Chicken - Microservicio de Pedidos (Serverless)
Arquitectura Event-Driven con AWS Step Functions, EventBridge y DynamoDB

Visión General
Este microservicio gestiona clientes y pedidos en un sistema 100% serverless, inspirado en Taco Bell.
Al crear un pedido:

Se guarda en DynamoDB
Se publica un evento en EventBridge
Step Functions ejecuta el flujo:
COOKING → PACKAGING → DELIVERY → DELIVERED


Arquitectura
text[API Gateway] 
     │
     ├── POST /orders → Lambda (create_order) → DynamoDB + EventBridge
     │
     └── EventBridge → Rule → Step Functions (OrderWorkflow)
                         │
                         ├── Lambda: process_cooking
                         ├── Lambda: process_packaging
                         ├── Lambda: process_delivery
                         └── Lambda: process_delivered → DynamoDB

Endpoints (HTTP API)



































MétodoRutaDescripciónPOST/customersCrear clienteGET/customers/{customerId}Ver clientePOST/ordersCrear pedido (dispara flujo)GET/orders/{customerId}Ver pedidos del clienteGET/order/{orderId}Ver pedido + cliente + pasos

Componentes AWS








































ServicioNombreFunciónDynamoDBCustomersTableClientesDynamoDBOrdersTablePedidos (PK, SK=INFO)DynamoDBStepsTableHistorial de pasosEventBridgePardosEventBusEventosStep FunctionsOrderWorkflowFlujo de cocinaIAM RoleLabRolePermisos

Flujo de un Pedido
mermaidgraph TD
    A[POST /orders] --> B[Guardar en OrdersTable]
    B --> C[Publicar OrderCreated → EventBridge]
    C --> D[Step Functions: OrderWorkflow]
    D --> E[Cooking Lambda]
    E --> F[Packaging Lambda]
    F --> G[Delivery Lambda]
    G --> H[Delivered Lambda]
    H --> I[Actualizar: status=COMPLETED]

Pruebas Rápidas (cURL)
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

# → Respuesta: {"orderId": "o1738795678"}

# 3. Esperar 15 segundos (flujo automático)

# 4. Ver pedido completo
curl https://2wmcf9zj7e.execute-api.us-east-1.amazonaws.com/order/o1738795678
Respuesta esperada:
json{
  "orderId": "o1738795678",
  "status": "COMPLETED",
  "currentStep": "DELIVERED",
  "total": 34.4,
  "customer": {"name": "Ana López"},
  "steps": ["COOKING", "PACKAGING", "DELIVERY", "DELIVERED"]
}

Verificación Manual
DynamoDB
bash# OrdersTable
aws dynamodb get-item --table-name OrdersTable \
  --key '{"PK": {"S": "TENANT#pardos#ORDER#o1738795678"}, "SK": {"S": "INFO"}}'

# StepsTable (4 pasos)
aws dynamodb query --table-name StepsTable \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TENANT#pardos#ORDER#o1738795678"}}'
Step Functions

Ir a: https://us-east-1.console.aws.amazon.com/states
Buscar: OrderWorkflow
Ver ejecución → 4 pasos en verde


Despliegue
bash# Instalar Serverless
npm install -g serverless

# Desplegar
sls deploy --stage dev

Estructura de Archivos
text.
├── handler.py          ← Lógica de Lambdas
├── serverless.yml      ← Infraestructura como código
└── README.md           ← Este archivo

Tecnologías Usadas





































TecnologíaUsoPython 3.13LambdasAWS LambdaFuncionesAPI Gateway (HTTP API)EndpointsDynamoDBBase de datos NoSQLEventBridgeEventosStep FunctionsOrquestaciónServerless FrameworkDespliegue

Notas Importantes

status es palabra reservada → usar #st en UpdateExpression
Decimal → float solo para EventBridge
GET /order/{id} → evita conflicto con /orders/{customerId}
ScanIndexForward=True → ordena por SK (usa timestamp)
