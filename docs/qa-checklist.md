# Checklist de Validación QA - TinkuBot

## 📋 Resumen

Checklist completo para validar que el sistema TinkuBot funciona correctamente después de los cambios implementados en el ambiente de QA.

## 🎯 Alcance

Validación del flujo completo de clientes incluyendo:
- Sistema de consentimiento implementado
- Búsqueda de proveedores
- Registro en base de datos
- Sistema de feedback

## ✅ Pre-requisitos de Ambiente

### Servicios Corriendo
- [ ] `whatsapp-service-clientes` (puerto 8005) - Healthy
- [ ] `ai-service-clientes` (puerto 5003) - Healthy
- [ ] `ai-service-proveedores` (puerto 5007) - Healthy
- [ ] Redis conectado y funcional
- [ ] Supabase accesible con credenciales correctas

### Verificación de Servicios
```bash
# Health checks
curl http://localhost:8005/health  # WhatsApp Clientes
curl http://localhost:5003/health  # AI Service Clientes
curl http://localhost:5007/health  # AI Service Proveedores
```

### Base de Datos
- [ ] Tabla `customers` existe y es accesible
- [ ] Tabla `consents` existe y está vacía o con datos de prueba
- [ ] Tabla `service_requests` accesible
- [ ] Tabla `task_queue` accesible

## 🧪 Escenarios de Prueba

### 1. Flujo Completo de Nuevo Cliente

#### Paso 1: Primer Contacto
- [ ] Enviar mensaje "hola" al bot de WhatsApp
- [ ] **Resultado esperado**: Bot solicita consentimiento con botones

#### Paso 2: Aceptación de Consentimiento
- [ ] Responder "Sí, acepto" (opción 1)
- [ ] **Resultado esperado**:
  - Mensaje de confirmación "✅ Gracias por aceptar"
  - Bot continúa con flujo normal de búsqueda
  - `customers.has_consent = true` en BD
  - Registro creado en tabla `consents`

#### Paso 3: Búsqueda de Servicio
- [ ] Enviar "necesito plomero en Quito"
- [ ] **Resultado esperado**:
  - Bot solicita ciudad (si no está clara)
  - Muestra opciones de proveedores disponibles
  - Registro en `service_requests`

#### Paso 4: Selección de Proveedor
- [ ] Seleccionar un proveedor de la lista
- [ ] **Resultado esperado**:
  - Mensaje con contacto del proveedor
  - Link `wa.me` funcional
  - Tarea de feedback programada en `task_queue`

### 2. Flujo de Rechazo de Consentimiento

#### Paso 1: Rechazo Inicial
- [ ] Enviar mensaje "hola" con número nuevo
- [ ] Responder "No, gracias" (opción 2)
- [ ] **Resultado esperado**:
  - Mensaje explicando que no puede compartir datos
  - Ofrece ayuda directa
  - `customers.has_consent = false` en BD
  - Registro de rechazo en `consents`

#### Paso 2: Reintento
- [ ] Enviar nuevo mensaje "hola"
- [ ] **Resultado esperado**: Vuelve a solicitar consentimiento

### 3. Cliente con Consentimiento Previo

#### Paso 1: Cliente Existente
- [ ] Usar número que ya tiene `has_consent = true`
- [ ] Enviar "hola"
- [ ] **Resultado esperado**: No solicita consentimiento, va directo a flujo de búsqueda

#### Paso 2: Cambio de Ciudad
- [ ] Enviar servicio y ciudad diferente
- [ ] **Resultado esperado**: Actualiza `customers.city` y `city_confirmed_at`

### 4. Casos Extremos

#### Comandos de Sistema
- [ ] Enviar "reset"
- [ ] **Resultado esperado**: Limpia ciudad, reinicia flujo
- [ ] Enviar mensaje inválido
- [ ] **Resultado esperado**: Respuesta de fallback amigable

#### Ubicación Geográfica
- [ ] Enviar ubicación compartida por WhatsApp
- [ ] **Resultado esperado**: Procesa coordenadas y las usa en búsqueda

## 🗄️ Validación de Base de Datos

### Queries de Validación

```sql
-- 1. Verificar clientes creados
SELECT phone_number, full_name, has_consent, city, created_at
FROM customers
ORDER BY created_at DESC
LIMIT 10;

-- 2. Verificar consentimientos registrados
SELECT c.phone_number, co.response, co.created_at, co.message_log->>'consent_timestamp'
FROM consents co
JOIN customers c ON co.user_id = c.id
ORDER BY co.created_at DESC
LIMIT 10;

-- 3. Verificar solicitudes de servicio
SELECT phone, profession, location_city, requested_at, suggested_providers
FROM service_requests
ORDER BY requested_at DESC
LIMIT 5;

-- 4. Verificar tareas programadas (feedback)
SELECT task_type, status, scheduled_at, payload
FROM task_queue
WHERE task_type = 'send_whatsapp'
ORDER BY scheduled_at DESC
LIMIT 5;
```

### Validaciones Esperadas
- [ ] Todos los clientes nuevos tienen registro en `customers`
- [ ] Todos los consentimientos tienen registro en `consents` con metadata completa
- [ ] `customers.has_consent` refleja correctamente el estado de consentimiento
- [ ] `service_requests` registra las búsquedas realizadas
- [ ] `task_queue` tiene tareas de feedback programadas

## 🔍 Validación de Metadata de Consentimiento

### Campos Requeridos en `consents.message_log`
Para cada registro de consentimiento verificar:

```json
{
  "consent_timestamp": "2025-01-XX...",  // ✅ Timestamp del consentimiento
  "phone": "+593998823053",             // ✅ Teléfono del cliente
  "message_id": "wamid...",              // ✅ ID del mensaje de WhatsApp
  "exact_response": "Sí, acepto",        // ✅ Respuesta exacta
  "consent_type": "provider_contact",   // ✅ Tipo de consentimiento
  "platform": "whatsapp",               // ✅ Plataforma
  "message_type": "text",                // ✅ Tipo de mensaje
  "device_type": "android"               // ✅ Tipo de dispositivo
}
```

### Checklist de Metadata
- [ ] Timestamp presente y válido
- [ ] Teléfono coincide con cliente
- [ ] Message_id de WhatsApp presente
- [ ] Respuesta exacta guardada
- [ ] Todos los campos obligatorios presentes

## 📊 Validación de Flujo de Feedback

### Proceso de Feedback
- [ ] Después de conectar con proveedor, esperar `FEEDBACK_DELAY_SECONDS`
- [ ] **Resultado esperado**: Bot envía mensaje de calificación
- [ ] Opciones de calificación: ⭐️1, ⭐️2, ⭐️3, ⭐️4, ⭐️5
- [ ] Validar que la respuesta se procesa correctamente

### Validación de Tareas
- [ ] Tarea creada en `task_queue` con tipo `send_whatsapp`
- [ ] Status cambia de `pending` → `completed`
- [ ] Timestamps registrados correctamente

## 🚨 Casos de Error y Recovery

### Escenarios de Error
- [ ] **Sin conexión a AI Service**: Bot responde con mensaje de fallback
- [ ] **Base de datos caída**: Sistema continúa funcionando con Redis
- [ ] **WhatsApp desconectado**: Requiere escanear QR nuevamente

### Recovery Tests
- [ ] Reiniciar servicio `ai-service-clientes` y verificar continuidad
- [ ] Reiniciar servicio `whatsapp-service-clientes` y verificar reconexión
- [ ] Limpiar Redis y verificar que los flujos se reinician correctamente

## 📈 Métricas de Éxito

### Indicadores Clave
- [ ] **Tasa de aceptación de consentimiento**: > 70%
- [ ] **Tiempo de respuesta del bot**: < 3 segundos
- [ ] **Disponibilidad del servicio**: > 95%
- [ ] **Errores de procesamiento**: < 1%

### Logs a Monitorear
```bash
# Logs clave a observar
docker-compose logs -f ai-service-clientes | grep -E "(consent|customers|consents)"
docker-compose logs -f whatsapp-service-clientes | grep -E "(QR|connected|message)"
```

## ✅ Criterios de Aprobación

El sistema pasa QA si cumple con:

1. **Funcionalidad Completa**:
   - [ ] Flujo de consentimiento funciona para 100% de nuevos clientes
   - [ ] Búsqueda de proveedores devuelve resultados correctos
   - [ ] Sistema de feedback opera según tiempo configurado

2. **Persistencia de Datos**:
   - [ ] Todos los clientes se registran correctamente
   - [ ] 100% de consentimientos se registran con metadata completa
   - [ ] No hay pérdida de datos en reinicios de servicios

3. **Experiencia de Usuario**:
   - [ ] Mensajes claros y profesionales
   - [ ] Tiempos de respuesta aceptables
   - [ ] Manejo adecuado de errores

4. **Estabilidad**:
   - [ ] Servicios se mantienen healthy durante pruebas
   - [ ] No hay memory leaks o consumo excesivo de recursos
   - [ ] Reconexión automática ante caídas

## 📝 Notas Finales

- **Documentación referenciada**: `docs/database-architecture.md`, `docs/consent-flow.md`
- **Ambiente de prueba**: QA (no producción)
- **Duración estimada**: 2-3 horas de testing completo
- **Reporte de incidencias**: Crear tickets para cualquier desviación

---

**Versión**: 1.0
**Fecha**: Enero 2025
**Estado**: Listo para ejecución en QA
**Próxima revisión**: Después de ciclo de producción