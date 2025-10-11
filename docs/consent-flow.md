# Flujo de Consentimiento - Implementación Real

## 📋 Resumen

Este documento describe el flujo de consentimiento actualmente implementado y funcionando en TinkuBot para el cumplimiento de normativas de protección de datos personales.

## 🎯 Objetivo del Flujo

Capturar el consentimiento explícito del cliente antes de compartir sus datos de contacto con proveedores de servicios, cumpliendo con requisitos de ley y manteniendo registro completo de las interacciones.

## 🔄 Flujo Completo Implementado

### 1. Detección de Cliente Sin Consentimiento

```python
# En ai-service-clientes/main.py líneas 966-978
customer_profile = get_or_create_customer(phone=phone)

# Validación de consentimiento
if not customer_profile:
    return await request_consent(phone)

# Si no tiene consentimiento, verificar si está respondiendo a la solicitud
if not customer_profile.get('has_consent'):
    selected = normalize_button(payload.get("selected_option"))
    if selected in ["1", "2"]:  # Respondiendo al consentimiento
        return await handle_consent_response(phone, customer_profile, selected, payload)
    else:
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

**Botones disponibles**:
- "Sí, acepto" (opción 1)
- "No, gracias" (opción 2)

### 3. Manejo de Respuestas

#### ✅ Si el cliente acepta (opción 1):

```python
# Líneas 457-493 en main.py
if selected_option == "1":  # "Sí, acepto"
    response = "accepted"
    message = "✅ Gracias por aceptar. Ahora puedo ayudarte a encontrar los mejores proveedores para ti."

    # Actualizar has_consent a TRUE
    supabase.table("customers").update({"has_consent": True}).eq(
        "id", customer_profile.get("id")
    ).execute()

    # Guardar registro legal en tabla consents
    consent_data = {
        "consent_timestamp": payload.get("timestamp"),
        "phone": payload.get("from_number"),
        "message_id": payload.get("message_id"),
        "exact_response": payload.get("content"),
        "consent_type": "provider_contact",
        "platform": "whatsapp",
        "message_type": payload.get("message_type"),
        "device_type": payload.get("device_type")
    }

    consent_record = {
        "user_id": customer_profile.get("id"),
        "user_type": "customer",
        "response": response,
        "message_log": json.dumps(consent_data, ensure_ascii=False),
    }
    supabase.table("consents").insert(consent_record).execute()
```

#### ❌ Si el cliente rechaza (opción 2):

```python
# Líneas 495-529
else:  # "No, gracias"
    response = "declined"
    message = """Entendido. Sin tu consentimiento no puedo compartir tus datos con proveedores.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""

    # Guardar registro legal igualmente con metadata completa
    consent_record = {
        "user_id": customer_profile.get("id"),
        "user_type": "customer",
        "response": response,
        "message_log": json.dumps(consent_data, ensure_ascii=False),
    }
    supabase.table("consents").insert(consent_record).execute()
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
  "exact_response": "Sí, acepto",
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

## 📋 Checklist de Validación para QA

- [ ] Clientes nuevos reciben solicitud de consentimiento
- [ ] Botones "Sí, acepto" y "No, gracias" funcionan correctamente
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