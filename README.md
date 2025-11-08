# Pardos Chicken - Microservicio de Pedidos (Serverless)  
**Arquitectura Event-Driven con AWS Step Functions, EventBridge y DynamoDB**

---

## Visión General
Este microservicio gestiona **clientes y pedidos** en un sistema **100% serverless**, inspirado en **Taco Bell**.  
Al crear un pedido:
1. Se guarda en **DynamoDB**
2. Se publica un evento en **EventBridge**
3. **Step Functions** ejecuta el flujo:  
   `COOKING → PACKAGING → DELIVERY → DELIVERED`

---

## Arquitectura

```text
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

Endpoints (HTTP API)
Método,Ruta,Descripción
POST,/customers,Crear cliente
GET,/customers/{customerId},Ver cliente
POST,/orders,Crear pedido (dispara flujo)
GET,/orders/{customerId},Ver pedidos del cliente
GET,/order/{orderId},Ver pedido + cliente + pasos

