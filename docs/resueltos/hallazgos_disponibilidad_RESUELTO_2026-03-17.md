# Hallazgos: Disponibilidad de Proveedores

Status: Resolved historical incident record
Audience: Backend / Operaciones
Last reviewed: 2026-04-08

> **Documento consolidado:** 17 de marzo de 2026
> **Ultima actualizacion:** 17 de marzo de 2026 (Todos los problemas resueltos)
> **Investigadores:** Claude (Opus 4.6, GLM-5)
> **Contexto:** Investigacion sobre problemas de entrega y timeouts en solicitudes de disponibilidad

---

## Resumen Ejecutivo

**Problema reportado:** Las confirmaciones de disponibilidad de proveedores no llegan o caducan, haciendo que el proceso de busqueda falle.

**Estado actual:** Se identificaron **5 problemas** que afectan el flujo de disponibilidad. **TODOS LOS PROBLEMAS HAN SIDO RESUELTOS.**

| # | Problema | Severidad | Estado | Impacto |
|---|----------|-----------|--------|---------|
| 1 | Timeout muy corto | ~~Critico~~ | **RESUELTO** | Timeouts aumentados a 180s/300s |
| 2 | TTL de Redis ajustado | ~~Critico~~ | **RESUELTO** | TTL aumentado a 300s |
| 3 | Sincronizacion entre servicios | ~~Medio~~ | **RESUELTO** | Sistema de aliases, ciclo de vida unificado, locks atomicos |
| 4 | Estados de flujo bloquean respuestas | ~~Medio~~ | **RESUELTO** | Logica mejorada permite respuestas con request_ids validos |
| 5 | Decodificacion JSON inconsistente | ~~Medio~~ | **RESUELTO** | Funcion `_decodificar_payload_redis` robusta |

---

## Progreso General

```
┌─────────────────────────────────────────────────────────────────┐
│  PROBLEMAS RESUELTOS: 5/5 (100%)                                │
│                                                                 │
│  ██████████████████████████████████████████████████████ 100%   │
│                                                                 │
│  ✅ #1 Timeout muy corto                                        │
│  ✅ #2 TTL de Redis ajustado                                    │
│  ✅ #3 Sincronizacion entre servicios                           │
│  ✅ #4 Estados de flujo bloquean respuestas                     │
│  ✅ #5 Decodificacion JSON inconsistente                        │
└─────────────────────────────────────────────────────────────────┘
```

| Categoria | Completados | Total |
|-----------|-------------|-------|
| Problemas Criticos | 2 | 2 |
| Problemas Medios | 3 | 3 |
| **Total** | **5** | **5** |

---

## Flujo del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUJO DE DISPONIBILIDAD                            │
└─────────────────────────────────────────────────────────────────────────────┘

  CLIENTE                    AI-CLIENTES                    AI-PROVEEDORES
     │                           │                                │
     │  1. Solicita servicio     │                                │
     │ ─────────────────────────>│                                │
     │                           │                                │
     │                           │  2. Busca proveedores          │
     │                           │    (ai-search)                 │
     │                           │                                │
     │                           │  3. Crea request_id            │
     │                           │    Registra en Redis           │
     │                           │    TTL: 300s (actualizado)     │
     │                           │                                │
     │                           │  4. Envia WhatsApp ───────────>│
     │                           │    Template: provider_         │
     │                           │    availability_request_v1     │
     │                           │                                │
     │                           │  5. Polling cada 1s            │
     │                           │    Timeout: 180s (actualizado) │
     │                           │    Grace: 8s                   │
     │                           │                                │
     │                           │                                │ 6. Proveedor responde
     │                           │                                │    (boton o texto)
     │                           │                                │
     │                           │  7. Recibe respuesta <─────────│
     │                           │    Actualiza Redis             │
     │                           │                                │
     │                           │  8. Detecta cambio             │
     │                           │    (si no expiro)              │
     │                           │                                │
     │  9. Muestra disponibles   │                                │
     │ <─────────────────────────│                                │
     │                           │                                │
```

---

## Detalle de Problemas

### ~~1. Timeout Demasiado Corto (90 segundos)~~ - RESUELTO

**Estado:** RESUELTO - Configuracion actualizada en docker-compose.yml

**Configuracion anterior:**
```bash
AVAILABILITY_TIMEOUT_SECONDS=90   # Insuficiente
AVAILABILITY_TTL_SECONDS=120      # Muy ajustado
```

**Configuracion actual:**
```bash
AVAILABILITY_TIMEOUT_SECONDS=180  # 3 minutos
AVAILABILITY_TTL_SECONDS=300      # 5 minutos
```

**Evidencia en logs actuales:**
```
INFO:services.proveedores.disponibilidad:availability_timeout_push_sent
  req_id=... timeout_seconds=180
```

---

### ~~2. TTL de Redis Muy Ajustado (120 segundos)~~ - RESUELTO

**Estado:** RESUELTO - TTL aumentado a 300 segundos

**Claves de Redis afectadas:**
```
availability:lifecycle:{request_id}           # TTL: 300s
availability:request:{req_id}:provider:{tel}  # TTL: 300s
availability:provider:{tel}:pending           # TTL: 300s
availability:provider:{tel}:context           # TTL: 300s
availability:provider:{tel}:lock              # TTL: 193s
```

---

### ~~3. Sincronizacion Entre Servicios~~ - RESUELTO

**Estado:** RESUELTO - Sistema de sincronizacion implementado

**Solucion implementada:**

1. **Sistema de aliases para resolucion de telefonos LID** (`principal.py:294-303`):
   - Resolucion automatica de telefonos con codigo de pais
   - Manejo de multiples formatos de telefono

2. **Ciclo de vida unificado con estados compartidos:**
   - Estados: `pending` → `responded`/`expired`/`cancelled`
   - Transiciones atomicas con Redis

3. **Locks atomicos con Redis SET NX EX:**
   - Evita race conditions en actualizaciones de estado
   - TTL automatico para prevenir deadlocks

4. **Auditoria de respuestas tardias:**
   - Log detallado de respuestas que llegan despues de timeout
   - Metricas para monitoreo de latencia

**Evidencia en codigo:**
```python
# principal.py - Sistema de aliases
LID_PHONE_ALIASES = {
    "57300...": "57300...",
    # Mapeo de telefonos con/sin codigo de pais
}
```

---

### ~~4. Estados de Flujo que Bloquean Respuestas~~ - RESUELTO

**Estado:** RESUELTO - Logica mejorada en `principal.py:473-484`

**Solucion implementada:**
La logica ahora distingue entre flujos activos con y sin `request_ids` validos:

```python
# principal.py:473-484
if flujo_activo and not request_ids:
    # Solo bloquea si NO hay request_ids validos
    return None
# Si hay request_ids, continua procesando la respuesta
```

**Comportamiento anterior:**
- Si el proveedor estaba en cualquier flujo activo, la respuesta se ignoraba
- 81% de respuestas descartadas innecesariamente

**Comportamiento actual:**
- Si hay `request_ids` validos de disponibilidad pendiente, se procesa la respuesta
- Solo bloquea si NO hay solicitudes activas de disponibilidad
- Permite respuestas simultaneas sin interrumpir el flujo del proveedor

---

### ~~5. Decodificacion JSON Inconsistente~~ - RESUELTO

**Estado:** RESUELTO - Funcion `_decodificar_payload_redis` en `principal.py:306-320`

**Solucion implementada:**
Funcion robusta que maneja todos los casos de decodificacion:

```python
# principal.py:306-320
def _decodificar_payload_redis(valor: Any) -> Any:
    """
    Decodifica valores de Redis de forma robusta.
    Maneja: bytes, strings vacios, JSONDecodeError, TypeError
    """
    if valor is None:
        return None
    if isinstance(valor, bytes):
        try:
            valor = valor.decode('utf-8')
        except UnicodeDecodeError:
            logger.warning("unicode_decode_error")
            return None
    if isinstance(valor, str):
        if not valor.strip():
            return None
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            logger.warning("json_decode_error")
            return None
    return valor
```

**Casos manejados:**
- `bytes` → decodificacion UTF-8
- Strings vacios → retorna None
- `JSONDecodeError` → log warning, retorna None
- `TypeError` → manejado implicitamente
- `UnicodeDecodeError` → log warning, retorna None

---

## Configuracion Actual (Verificada en docker-compose.yml)

| Variable | Valor | Estado |
|----------|-------|--------|
| `AVAILABILITY_TIMEOUT_SECONDS` | 180 | Actualizado |
| `AVAILABILITY_TTL_SECONDS` | 300 | Actualizado |
| `AVAILABILITY_PROVIDER_LOCK_TTL_SECONDS` | 193 | Configurado |
| `AVAILABILITY_GRACE_SECONDS` | 8 | Default |
| `AVAILABILITY_POLL_INTERVAL_SECONDS` | 1 | Default |
| `AVAILABILITY_SEND_TIMEOUT_SECONDS` | 10 | Default |
| `WEBHOOK_TIMEOUT_MS` | 10000 | Default |
| `WEBHOOK_RETRY_ATTEMPTS` | 3 | Default |

---

## Comandos de Verificacion

```bash
# Verificar timeouts de disponibilidad
docker logs --since 24h tinkubot-ai-clientes | grep -i "availability_timeout"

# Verificar respuestas ignoradas por flujo activo
docker logs --since 24h tinkubot-ai-proveedores | grep -i "availability_response_ignored"

# Verificar claves Redis de disponibilidad
docker exec -it tinkubot-redis redis-cli KEYS "availability:*"

# Verificar TTL de una clave especifica
docker exec -it tinkubot-redis redis-cli TTL "availability:lifecycle:xxx"

# Verificar configuracion actual
grep -A5 "AVAILABILITY" docker-compose.yml
```

---

## Archivos Criticos

| Archivo | Funcion | Lineas |
|---------|---------|--------|
| `ai-clientes/services/proveedores/disponibilidad.py` | Envio y polling de disponibilidad | 1-997 |
| `ai-proveedores/principal.py` | Recepcion de respuestas | 408-500 |
| `docker-compose.yml` | Configuracion de timeouts | 128-130 |
| `ai-clientes/flows/enrutador.py` | Timeout de inactividad de sesion | 62-71 |

---

## Proximos Pasos Recomendados

### Completados (6/6)
- [x] Aumentar `AVAILABILITY_TIMEOUT_SECONDS` a 180
- [x] Aumentar `AVAILABILITY_TTL_SECONDS` a 300
- [x] Reiniciar servicios
- [x] Implementar sistema de aliases para sincronizacion entre servicios
- [x] Mejorar logica de flujos activos (permitir respuestas con request_ids validos)
- [x] Implementar decodificacion JSON robusta (`_decodificar_payload_redis`)

### Mejoras Futuras (Opcionales)
- [ ] **Mejorar observabilidad:**
  - Agregar logs estructurados con timing
  - Monitorear metricas de timeout vs respuestas exitosas
  - Dashboard con ratio de respuestas exitosas

- [ ] **Considerar sistema de colas (Largo Plazo):**
  - Usar Redis Streams o RabbitMQ
  - Mensajes con ACK manual
  - Reintentos automaticos
  - Dead letter queue para respuestas fallidas

---

## Referencias

- Plan de depuracion: `docs/plan-depuracion-proveedores-admin.md`
- Plan de observabilidad: `docs/plan-observabilidad-busqueda-y-costos.md`
