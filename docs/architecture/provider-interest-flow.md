# Provider Interest Coordination Flow

## Objetivo

Lograr que TinkuBot conecte necesidades de clientes con proveedores interesados en tiempo real, reduciendo fricción y asegurando disponibilidad confirmada antes de entregarle opciones al cliente.

## Fases de implementación

### Fase 0 – Fundamentos compartidos
- Definir payloads de eventos y contractos API entre `ai-service-clientes` y `ai-service-proveedores`.
- Preparar utilidades de logging/trace en ambos servicios para auditar cada solicitud.

### Fase 1 – Simplificación del flujo en AI Clientes
- Pedir únicamente servicio y ciudad (ciudad solo la primera vez); eliminar prompt de urgencia.
- Incorporar almacenamiento de ciudad preferida en la sesión para reutilizarla.
- Ajustar prompts de resultados para mostrar únicamente proveedores disponibles y permitir selección directa.

### Fase 2 – Orquestación de invitaciones sin cola externa
- Implementar en `ai-service-clientes` un coordinador que:
  - Solicite candidatos a `ai-service-proveedores` filtrando por ciudad y `available = True`.
  - Genere un `request_id` y dispare eventos `provider.invite.created` a través de un stub (por ahora en memoria/REST).
  - Espere respuestas hasta 3 minutos o hasta recibir 3 interesados; pasado el plazo, use fallback por rating.
- Implementar en `ai-service-proveedores` un handler para `provider.invite.created` que:
  - Envíe la invitación por WhatsApp con opciones "1. Me interesa" / "2. No puedo".
  - Procese la respuesta del proveedor y publique `provider.invite.responded`.
- Manejar respuestas tardías agradeciendo y notificando que la solicitud ya se asignó.

### Fase 3 – Asignación y comunicación
- `ai-service-clientes` muestra al cliente los proveedores interesados (ordenados por tiempo de respuesta y rating). Si no hay interesados, devuelve los 3 mejores ratings disponibles.
- Al recibir la elección del cliente, se emite `provider.assignment.confirmed` y se comparte el contacto.
- `ai-service-proveedores` notifica al proveedor elegido y marca a los demás en standby.
- Registrar `provider.assignment.closed` cuando el caso se concreta o se cancela.

### Fase 4 – Introducción de broker de eventos
- Sustituir el stub por RabbitMQ o Redis Streams para transportar eventos.
- Garantizar idempotencia con `event_id` y `trace_id`.
- Incorporar DLQ/reintentos para manejar fallos transitorios.

### Fase 5 – Métricas y monetización
- Medir: tiempo medio de respuesta de proveedores, ratio de interesados, conversiones por profesión/ciudad.
- Establecer límites de invitaciones simultáneas por proveedor y reglas de facturación por "lead" confirmado.
- Ajustar el estado de disponibilidad automáticamente según el flujo (ej. proveedor con demasiadas invitaciones pendientes pasa a "ocupado").

## Esquema de eventos

### `provider.invite.created`
```json
{
  "event_id": "evt-uuid",
  "trace_id": "req-uuid",
  "request_id": "req-123",
  "client_phone": "+593999000111",
  "profession": "Electricista",
  "city": "Quito",
  "provider_id": "prov-45",
  "provider_phone": "+593888777666",
  "deadline_at": "2024-05-28T15:03:22Z",
  "invited_at": "2024-05-28T15:00:22Z"
}
```

### `provider.invite.responded`
```json
{
  "event_id": "evt-uuid",
  "trace_id": "req-uuid",
  "request_id": "req-123",
  "provider_id": "prov-45",
  "response": "interested",  // interested | declined | timeout
  "response_at": "2024-05-28T15:01:05Z",
  "meta": {
    "message_id": "wamid-1234",
    "raw_answer": "1"
  }
}
```

### `provider.assignment.confirmed`
```json
{
  "event_id": "evt-uuid",
  "trace_id": "req-uuid",
  "request_id": "req-123",
  "provider_id": "prov-45",
  "client_phone": "+593999000111",
  "confirmed_at": "2024-05-28T15:02:45Z",
  "channel": "whatsapp"
}
```

### `provider.assignment.closed`
```json
{
  "event_id": "evt-uuid",
  "trace_id": "req-uuid",
  "request_id": "req-123",
  "provider_id": "prov-45",
  "status": "completed",  // completed | cancelled
  "closed_at": "2024-05-29T09:15:00Z",
  "meta": {
    "reason": "Cliente confirmó visita"
  }
}
```

## Reglas operativas
- Timeout máximo: 3 minutos o hasta reunir 3 respuestas "interested".
- Fallback: si nadie responde, mostrar al cliente los 3 mejores ratings disponibles.
- Respuestas tardías: agradecer al proveedor y avisar que la solicitud ya fue asignada; registrar evento para métricas.
- Control de carga: limitar invitaciones simultáneas por proveedor; al alcanzar el límite, no emitir nuevos `provider.invite.created` hasta liberar un slot.
- Persistencia de ciudad: `ai-service-clientes` guarda la última ciudad confirmada para reusarla.

## Próximos pasos inmediatos
1. Ajustar `ai-service-clientes` para el flujo simplificado (sin prompt de urgencia).
2. Implementar stub de eventos y handlers básicos en ambos servicios.
3. Validar end-to-end con un caso real antes de introducir el broker.
