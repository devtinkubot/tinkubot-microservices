# Análisis Completo del Flujo de ai-proveedores

## Archivos Principales que Orquestan el Flujo

### 1. **Punto de Entrada Principal**
- **`principal.py`**: Handler HTTP que recibe los webhooks de WhatsApp
  - Función: `handler_whatsapp()`
  - Obtiene el flujo desde Redis
  - Llama al router para procesar el mensaje
  - Persiste el flujo actualizado

### 2. **Router del Sistema (El Cerebro)**
- **`flows/router.py`**: `manejar_mensaje()`
  - **Controla TODO el flujo del sistema**
  - Maneja palabras de reset
  - **Detecta timeout de inactividad (5 minutos / 300 segundos)**
  - Sincroniza el flujo con el perfil del proveedor
  - Determina el estado de registro
  - Enruta al manejador correspondiente según el estado actual

### 3. **Gestión de Sesión y Estados**
- **`services/sesion_proveedor.py`**:
  - `sincronizar_flujo_con_perfil()`: Sincroniza datos del flujo con el perfil persistido en Supabase
  - `resolver_estado_registro()`: Determina si el usuario está registrado
  - `manejar_estado_inicial()`: Resuelve la primera interacción cuando no hay estado
  - `manejar_pendiente_revision()`: Maneja proveedores pendientes de verificación
  - `manejar_aprobacion_reciente()`: Notifica cuando un perfil pasa de pendiente a verificado

### 4. **Gestores de Estados (Handlers)**
- **`flows/gestores_estados/`**: Cada archivo maneja un estado específico:
  - `gestor_consentimiento.py`: Estado `awaiting_consent`
  - `gestor_menu.py`: Estado `awaiting_menu_option`
  - `gestor_espera_ciudad.py`: Estado `awaiting_city`
  - `gestor_espera_nombre.py`: Estado `awaiting_name`
  - `gestor_espera_especialidad.py`: Estado `awaiting_specialty`
  - `gestor_confirmacion_servicios.py`: Estado `awaiting_services_confirmation`
  - `gestor_espera_experiencia.py`: Estado `awaiting_experience`
  - `gestor_espera_correo.py`: Estado `awaiting_email`
  - `gestor_espera_red_social.py`: Estado `awaiting_social_media`
  - `gestor_documentos.py`: Estados de documentación (DNI, selfie)

### 5. **Almacenamiento de Sesión**
- **`flows/sesion/gestor_flujo.py`**:
  - `obtener_flujo(telefono)`: Obtiene el flujo desde Redis
  - `establecer_flujo(telefono, datos)`: Guarda el flujo en Redis con TTL
  - `reiniciar_flujo(telefono)`: Elimina el flujo de Redis

### 6. **Mensajes y Templates**
- **`templates/sesion/manejo.py`**: Mensajes de timeout y reinicio
- **`templates/consentimiento/mensajes.py`**: Mensajes de consentimiento
- **`templates/registro/`**: Mensajes de registro y validaciones
- **`templates/interfaz/`**: Componentes de interfaz (menús, etc.)

---

## Flujo Completo de Registro

### Estados del Flujo (en orden):

```
1. awaiting_consent
   ↓ (usuario acepta)
2. awaiting_menu_option
   ↓ (usuario selecciona "1" - Registro)
3. awaiting_city
   ↓ (usuario ingresa ciudad)
4. awaiting_name
   ↓ (usuario ingresa nombre)
5. awaiting_specialty
   ↓ (usuario ingresa servicios)
6. awaiting_services_confirmation
   ↓ (usuario confirma servicios)
7. awaiting_experience
   ↓ (usuario ingresa experiencia o "omitir")
8. awaiting_email
   ↓ (usuario ingresa email o "omitir")
9. awaiting_social_media
   ↓ (usuario ingresa redes o "omitir")
10. awaiting_dni_front_photo
    ↓ (usuario envía foto frontal DNI)
11. awaiting_dni_back_photo
    ↓ (usuario envía foto trasera DNI)
12. awaiting_face_photo
    ↓ (usuario envía selfie)
13. confirm
    ↓ (usuario confirma datos)
14. awaiting_menu_option (usuarioregistrado - 5 opciones)
```

---

## Mecanismo de Timeout de Inactividad

### Ubicación: `flows/router.py:89-123`

```python
ahora_utc = datetime.utcnow()
ahora_iso = ahora_utc.isoformat()
ultima_vista_cruda = flujo.get("last_seen_at_prev")

if ultima_vista_cruda:
    try:
        ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda)
        if (ahora_utc - ultima_vista_dt).total_seconds() > 300:  # 5 minutos
            # 1. Reiniciar el flujo en Redis
            await reiniciar_flujo(telefono)

            # 2. Limpiar y actualizar timestamps
            flujo.clear()
            flujo.update({
                "last_seen_at": ahora_iso,
                "last_seen_at_prev": ahora_iso,
            })

            # 3. Sincronizar con perfil del proveedor
            flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
            _, esta_registrado_timeout, _, _ = resolver_estado_registro(flujo, perfil_proveedor)

            # 4. Establecer estado según situación del usuario
            flujo["state"] = "awaiting_menu_option"

            # 5. Enviar mensajes de timeout + menú
            mensajes_timeout = [
                {"response": informar_timeout_inactividad()},  # "No tuve respuesta y reinicié..."
                {"response": construir_menu_principal(esta_registrado=esta_registrado_timeout)}
            ]
            return {
                "response": {"success": True, "messages": mensajes_timeout},
                "new_flow": flujo,
                "persist_flow": True,
            }
    except Exception:
        pass  # ⚠️ SILENCIA ERRORES
```

### Comportamiento Esperado:

**Cuando hay timeout (> 5 minutos de inactividad):**

1. **Usuario NO registrado**:
   - Mensaje: "No tuve respuesta y reinicié la conversación..."
   - Menú: 2 opciones (1) Registro, 2) Salir)

2. **Usuario SÍ registrado**:
   - Mensaje: "No tuve respuesta y reinicié la conversación..."
   - Menú: 5 opciones (Servicios, Selfie, Redes, Eliminar, Salir)

### Actualización de Timestamps:
- Cada mensaje actualiza `last_seen_at` y `last_seen_at_prev`
- El timeout se calcula comparando `ahora_utc` con `last_seen_at_prev`

---

## Problema Reportado

### Síntoma:
El mensaje de timeout `informar_timeout_inactividad()` **ya no aparece** después de 5 minutos de inactividad.

### Posibles Causas:

1. **Excepción silenciada**: El bloque `except Exception: pass` en router.py:122-123 podría estar ocultando un error
2. **Flujo no persistido**: Si `persist_flow: False`, el flujo no se guarda en Redis
3. **Timestamps no actualizados**: Si `last_seen_at_prev` no se establece correctamente
4. **Sincronización incorrecta**: Si `sincronizar_flujo_con_perfil()` o `resolver_estado_registro()` fallan

### Código Actual:
```python
# Líneas 125-126 de router.py
flujo["last_seen_at"] = ahora_iso
flujo["last_seen_at_prev"] = flujo.get("last_seen_at", ahora_iso)
```

⚠️ **Nota**: `last_seen_at_prev` se establece con el valor anterior de `last_seen_at` o `ahora_iso` si no existe. En el primer mensaje de un flujo nuevo, ambos timestamps serán iguales.

---

## Debugging Sugerido

### 1. Agregar logging para ver si se detecta timeout:

```python
# En router.py:95
if (ahora_utc - ultima_vista_dt).total_seconds() > 300:
    logger.info(f"⏰ TIMEOUT DETECTADO para {telefono}")
    logger.info(f"Última vista: {ultima_vista_dt}, Ahora: {ahora_utc}")
    logger.info(f"Diferencia: {(ahora_utc - ultima_vista_dt).total_seconds()} segundos")
```

### 2. Verificar que el bloque try-except no esté silenciando errores:

```python
# En router.py:122
except Exception as e:
    logger.error(f"❌ Error procesando timeout: {e}")
    import traceback
    logger.error(traceback.format_exc())
```

### 3. Verificar persistencia del flujo:

Revisar que después de cada mensaje, el flujo se guarde correctamente en Redis con los timestamps actualizados.

---

## Archivos de Configuración

- **`config/configuracion.py`**: TTL del flujo en Redis, configuración de timeouts
- **`infrastructure/redis/cliente_redis.py`**: Cliente de Redis para guardar/recuperar flujos

---

## Resumen Ejecutivo

### El Sistema Funciona Así:

1. **Llega mensaje WhatsApp** → `principal.py`
2. **Obtiene flujo desde Redis** → `gestor_flujo.py`
3. **Procesa mensaje** → `router.py`
   - Verifica timeout (5 min)
   - Sincroniza con perfil
   - Enruta al handler correcto
4. **Handler procesa según estado** → `gestores_estados/*.py`
5. **Guarda flujo actualizado** → Redis
6. **Envía respuesta** → WhatsApp

### El Problema del Timeout:

El código de timeout **EXISTE y está ACTIVO** en router.py:89-123, pero el mensaje de timeout **no aparece**. Esto sugiere que:
- O bien el bloque try-except está capturando una excepción silenciosamente
- O el flujo se está reiniciando por otro motivo antes de llegar a la lógica de timeout
- O los timestamps no se están guardando correctamente en Redis

### Próximos Pasos Recomendados:

1. Agregar logging extensivo en el bloque de timeout
2. Verificar que los timestamps se guarden correctamente en Redis
3. Revisar si hay otros puntos donde se esté reiniciando el flujo
4. Verificar el TTL del flujo en Redis
