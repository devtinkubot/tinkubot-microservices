# Flujo de Consentimiento - Implementación Real

## 📋 Resumen

Este documento describe el flujo de consentimiento actualmente implementado y funcionando en TinkuBot para el cumplimiento de normativas de protección de datos personales.

## 🎯 Objetivo del Flujo

Capturar el consentimiento explícito del cliente antes de compartir sus datos de contacto con proveedores de servicios, cumpliendo con requisitos de ley y manteniendo registro completo de las interacciones.

## 🔄 Flujo Completo Implementado

### 1. Detección de Cliente Sin Consentimiento

```python
# ai-service-clientes/main.py (handle_whatsapp_message)
customer_profile = get_or_create_customer(phone=phone)

# Validación de consentimiento
if not customer_profile:
    return await request_consent(phone)

if not customer_profile.get("has_consent"):
    selected = normalize_button(payload.get("selected_option"))
    text_content = (payload.get("content") or "").strip()
    text_numeric_option = normalize_button(text_content)

    if selected in {"1", "2"}:
        return await handle_consent_response(phone, customer_profile, selected, payload)

    if text_numeric_option in {"1", "2"}:
        return await handle_consent_response(
            phone, customer_profile, text_numeric_option, payload
        )

    if interpret_yes_no(text_content) is not None:
        mapped = "1" if interpret_yes_no(text_content) else "2"
        return await handle_consent_response(phone, customer_profile, mapped, payload)

    return await request_consent(phone)
```

### 2. Mensaje de Solicitud de Consentimiento

**Contenido del mensaje** (templates/prompts.py):
```text
Para poder conectararte con proveedores de servicios, necesito tu consentimiento para compartir tus datos de contacto únicamente con los profesionales seleccionados.

📋 *Información que compartiremos:*
• Tu número de teléfono
• Ciudad donde necesitas el servicio
• Tipo de servicio que solicitas

🔒 *Tus datos están seguros y solo se usan para esta consulta.*

*¿Aceptas compartir tus datos con proveedores?*
```

**Bloque numérico y recordatorio**:
```
..................
1 Acepto
2 No acepto

..................
```

**Mensaje de seguimiento**:
```
*Responde con el número de tu opción:*
```

> ℹ️ `request_consent` devuelve ambos textos en una sola respuesta (`{"messages": [...]}`), por lo que WhatsApp envía primero el bloque explicativo y a continuación el recordatorio.

### 3. Manejo de Respuestas

#### ✅ Si el cliente acepta (opción 1):

```python
# ai-service-clientes/main.py (handle_consent_response)
if selected_option in ["1", "Acepto"]:
    supabase.table("customers").update({"has_consent": True}).eq(
        "id", customer_profile.get("id")
    ).execute()

    consent_data = {
        "consent_timestamp": payload.get("timestamp"),
        "phone": payload.get("from_number"),
        "message_id": payload.get("message_id"),
        "exact_response": payload.get("content"),
        "consent_type": "provider_contact",
        "platform": "whatsapp",
        "message_type": payload.get("message_type"),
        "device_type": payload.get("device_type"),
    }

    supabase.table("consents").insert(
        {
            "user_id": customer_profile.get("id"),
            "user_type": "customer",
            "response": "accepted",
            "message_log": json.dumps(consent_data, ensure_ascii=False),
        }
    ).execute()

    return {"response": INITIAL_PROMPT}
```

#### ❌ Si el cliente rechaza (opción 2):

```python
# Rama de rechazo en handle_consent_response
response = "declined"
message = """Entendido. Sin tu consentimiento no puedo compartir tus datos con proveedores.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""

supabase.table("consents").insert(
    {
        "user_id": customer_profile.get("id"),
        "user_type": "customer",
        "response": response,
        "message_log": json.dumps(consent_data, ensure_ascii=False),
    }
).execute()

return {"response": message}
```

## 🗃️ Estructura de Datos

### Tabla `customers` - Estado de Consentimiento

```sql
-- Campo principal para control de flujo
has_consent BOOLEAN DEFAULT false
```

### Tabla `consents` - Registro Legal Completo

```sql
CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES customers(id),
    user_type VARCHAR(20) DEFAULT 'customer',
    response VARCHAR(20) NOT NULL,  -- 'accepted' o 'declined'
    message_log JSONB NOT NULL,     -- Metadata completa
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Metadata Almacenada (message_log)

```json
{
  "consent_timestamp": "2025-01-11T15:30:00.000Z",
  "phone": "+593998823053",
  "message_id": "wamid.HBgLNTkzOTg4MjMwNTNVAgASGBQzQjI4RDI1QjBGMEYxQzg",
  "exact_response": "Acepto",
  "consent_type": "provider_contact",
  "platform": "whatsapp",
  "message_type": "text",
  "device_type": "android"
}
```

## 🔄 Estados del Flujo

### Estados del Cliente (customers.has_consent)

1. **NULL/Nuevo**: Cliente nunca ha interactuado → Mostrar solicitud de consentimiento
2. **false**: Cliente ha rechazado consentimiento → Bloquear flujo, ofrecer ayuda directa
3. **true**: Cliente ha aceptado consentimiento → Continuar con flujo normal de búsqueda

### Estados de Registro (consents.response)

1. **"accepted"**: Consentimiento otorgado
2. **"declined"**: Consentimiento rechazado

## 📊 Estadísticas y Métricas

### Queries Útiles para Monitoreo

```sql
-- Total de clientes con consentimiento
SELECT
    COUNT(*) as total_clientes,
    COUNT(CASE WHEN has_consent = true THEN 1 END) as con_consentimiento,
    COUNT(CASE WHEN has_consent = false OR has_consent IS NULL THEN 1 END) as sin_consentimiento,
    ROUND(COUNT(CASE WHEN has_consent = true THEN 1 END) * 100.0 / COUNT(*), 2) as porcentaje_aceptacion
FROM customers;

-- Registros de consentimiento por fecha
SELECT
    DATE(created_at) as fecha,
    response,
    COUNT(*) as cantidad
FROM consents
GROUP BY DATE(created_at), response
ORDER BY fecha DESC;

-- Últimos consentimientos registrados
SELECT
    c.phone_number,
    co.response,
    co.created_at,
    co.message_log->>'consent_timestamp' as consent_timestamp
FROM consents co
JOIN customers c ON co.user_id = c.id
ORDER BY co.created_at DESC
LIMIT 10;
```

## 🛡️ Características de Seguridad

### 1. **No Persistencia de Datos Sensibles**
- El sistema no almacena contenido completo de conversaciones
- Solo se guarda metadata necesaria para cumplimiento legal

### 2. **Registro Completo de Consentimientos**
- Timestamp exacto del consentimiento
- ID del mensaje de WhatsApp
- Respuesta exacta del usuario
- Plataforma y tipo de dispositivo

### 3. **Control de Acceso**
- Los datos solo se comparten con proveedores seleccionados
- No hay acceso masivo a información de clientes

## 🚀 Proceso de Testing del Flujo

### Escenarios de Prueba

1. **Cliente Nuevo sin Consentimiento**
   - Enviar mensaje inicial
   - Verificar que se solicite consentimiento
   - Aceptar y continuar flujo normal

2. **Cliente que Rechaza Consentimiento**
   - Rechazar solicitud
   - Verificar mensaje de despedida
   - Intentar nuevo contacto y mostrar solicitud nuevamente

3. **Cliente con Consentimiento Previo**
   - Enviar nuevo mensaje
   - No mostrar solicitud de consentimiento
   - Continuar directamente a flujo de búsqueda

4. **Validación de Registro Legal**
   - Verificar creación de registro en `consents`
   - Validar metadata completa almacenada
   - Comprobar actualización de `customers.has_consent`

5. **Reset Manual para QA**
   - Enviar `reset`
   - Confirmar que el flujo responde "Nueva sesión iniciada."
   - Verificar en Supabase que `has_consent` vuelve a `false` para ese cliente

## 📋 Checklist de Validación para QA

- [ ] Clientes nuevos reciben solicitud de consentimiento
- [ ] Opciones "1 Acepto" y "2 No acepto" funcionan correctamente
- [ ] Consentimientos aceptados actualizan `customers.has_consent = true`
- [ ] Consentimientos rechazados actualizan `customers.has_consent = false`
- [ ] Todos los consentimientos se registran en tabla `consents`
- [ ] Metadata completa se almacena en `message_log`
- [ ] Clientes con consentimiento previo no ven solicitud nuevamente
- [ ] Clientes que rechazan pueden reintentar más tarde
- [ ] El flujo normal continúa después de aceptar consentimiento

---

**Estado**: ✅ Implementado y funcionando en producción
**Próxima revisión**: Después de ciclo completo de QA
**Responsable**: Equipo de desarrollo TinkuBot
