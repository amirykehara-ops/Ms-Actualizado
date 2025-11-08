🐔 Pardos Chicken - Microservicio de Pedidos (Serverless)
Arquitectura Event-Driven con AWS Step Functions, EventBridge y DynamoDB
🧭 Visión General

Este microservicio gestiona clientes y pedidos en un sistema 100% serverless, inspirado en la arquitectura de Taco Bell.
Al crear un pedido:

Se guarda en DynamoDB

Se publica un evento en EventBridge

Step Functions ejecuta el flujo completo:
COOKING → PACKAGING → DELIVERY → DELIVERED

🏗️ Arquitectura
[API Gateway] 
     │
     ├── POST /orders → Lambda (create_order) → DynamoDB + EventBridge
     │
     └── EventBridge → Rule → Step Functions (OrderWorkflow)
                         │
                         ├── Lambda: process_cooking
                         ├── Lambda: process_packaging
                         ├── Lambda: process_delivery
                         └── Lambda: process_delivered → DynamoDB

🔗 Endpoints (HTTP API)
Método	Ruta	Descripción
POST	/customers	Crear cliente
GET	/customers/{customerId}	Ver cliente
POST	/orders	Crear pedido (dispara flujo)
GET	/orders/{customerId}	Ver pedidos del cliente
GET	/order/{orderId}	Ver pedido + cliente + pasos

☁️ Componentes AWS
Servicio	Nombre	Función
DynamoDB	CustomersTable	Clientes
DynamoDB	OrdersTable	Pedidos (PK, SK=INFO)
DynamoDB	StepsTable	Historial de pasos
EventBridge	PardosEventBus	Enrutamiento de eventos
Step Functions	OrderWorkflow	Flujo del pedido
IAM Role	LabRole	Permisos de ejecución

🔄 Flujo de un Pedido
sequenceDiagram
    participant API as API Gateway
    participant Lambda as Lambda create_order
    participant DB as OrdersTable
    participant EB as EventBridge
    participant SF as Step Functions
    participant Cooking as process_cooking
    participant Packaging as process_packaging
    participant Delivery as process_delivery
    participant Delivered as process_delivered

    API->>Lambda: POST /orders
    Lambda->>DB: Guardar pedido en OrdersTable
    Lambda->>EB: Publicar evento OrderCreated
    EB->>SF: Disparar flujo OrderWorkflow
    SF->>Cooking: COOKING
    SF->>Packaging: PACKAGING
    SF->>Delivery: DELIVERY
    SF->>Delivered: DELIVERED
    Delivered->>DB: Actualizar status=COMPLETED

⚙️ Pruebas Rápidas (cURL)
# 1. Crear cliente
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

# → Respuesta esperada:
# {"orderId": "o1738795678"}

# 3. Esperar ~15 segundos (flujo automático)

# 4. Ver pedido completo
curl https://2wmcf9zj7e.execute-api.us-east-1.amazonaws.com/order/o1738795678

🧾 Respuesta esperada:
{
  "orderId": "o1738795678",
  "status": "COMPLETED",
  "currentStep": "DELIVERED",
  "total": 34.4,
  "customer": {"name": "Ana López"},
  "steps": ["COOKING", "PACKAGING", "DELIVERY", "DELIVERED"]
}

🔍 Verificación Manual
DynamoDB
# OrdersTable
aws dynamodb get-item --table-name OrdersTable \
  --key '{"PK": {"S": "TENANT#pardos#ORDER#o1738795678"}, "SK": {"S": "INFO"}}'

# StepsTable (4 pasos)
aws dynamodb query --table-name StepsTable \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TENANT#pardos#ORDER#o1738795678"}}'

Step Functions

👉 Ir a: https://us-east-1.console.aws.amazon.com/states

Buscar OrderWorkflow → Ver ejecución → Debe mostrar 4 pasos en verde

🚀 Despliegue
# Instalar Serverless
npm install -g serverless

# Desplegar con entorno de desarrollo
sls deploy --stage dev

🗂️ Estructura de Archivos
.
├── handler.py          ← Lógica de Lambdas
├── serverless.yml      ← Infraestructura como código (IaC)
└── README.md           ← Este documento

🧠 Tecnologías Usadas
Tecnología	Uso
Python 3.13	Lenguaje principal
AWS Lambda	Funciones sin servidor
API Gateway (HTTP API)	Endpoints REST
DynamoDB	Base de datos NoSQL
EventBridge	Sistema de eventos
Step Functions	Orquestación de procesos
Serverless Framework	Despliegue automatizado
⚠️ Notas Importantes

status es palabra reservada → usar #st en UpdateExpression

Decimal debe convertirse a float para eventos de EventBridge

GET /order/{id} evita conflicto con /orders/{customerId}

ScanIndexForward=True → ordena por SK (timestamp)

✅ Estado Final

💡 Listo para Producción
Automático, escalable y totalmente serverless.
Funciona como Taco Bell, pero con sabor a Pardos Chicken 🍗🔥
