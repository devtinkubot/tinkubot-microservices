# Ejemplo de Integración del OrquestadorConversacional

Este documento muestra cómo integrar el `OrquestadorConversacional` en `main.py` para reemplazar la lógica del endpoint `/handle-whatsapp-message`.

## 1. Instanciación del Orquestador

En `main.py`, después de inicializar todas las dependencias, crear la instancia del orquestador:

```python
from services.orquestador_conversacion import OrquestadorConversacional

# Inicializar orquestador conversacional
orquestador = OrquestadorConversacional(
    redis_client=redis_client,
    supabase=supabase,
    session_manager=session_manager,
    coordinador_disponibilidad=coordinador_disponibilidad,
    logger=logger,
)

# Inyectar callbacks para evitar dependencias circulares
orquestador.inyectar_callbacks(
    get_or_create_customer=get_or_create_customer,
    request_consent=request_consent,
    handle_consent_response=handle_consent_response,
    reset_flow=reset_flow,
    get_flow=get_flow,
    set_flow=set_flow,
    update_customer_city=update_customer_city,
    check_if_banned=check_if_banned,
    validate_content_with_ai=validate_content_with_ai,
    search_providers=search_providers,
    send_provider_prompt=send_provider_prompt,
    send_confirm_prompt=send_confirm_prompt,
    clear_customer_city=clear_customer_city,
    clear_customer_consent=clear_customer_consent,
    formal_connection_message=formal_connection_message,
    schedule_feedback_request=schedule_feedback_request,
    send_whatsapp_text=send_whatsapp_text,
)
```

## 2. Endpoint Simplificado

Reemplazar el endpoint actual con esta versión simplificada:

```python
@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp.

    Este endpoint ahora delega toda la lógica de orquestación al
    OrquestadorConversacional, manteniendo solo la capa HTTP.
    """
    try:
        result = await orquestador.procesar_mensaje_whatsapp(payload)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error manejando mensaje WhatsApp: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error handling WhatsApp message: {str(e)}"
        )
```

## 3. Funciones Auxiliares que Permanecen en main.py

Las siguientes funciones NO se movieron al orquestador y deben permanecer en main.py:

### Funciones de Manejo de Flujo
- `reset_flow(phone: str)` - Reinicia el flujo de un usuario
- `get_flow(phone: str) -> Dict[str, Any]` - Obtiene el flujo actual
- `set_flow(phone: str, data: Dict[str, Any])` - Guarda el flujo

### Funciones de Cliente
- `get_or_create_customer(phone: str) -> Dict[str, Any]` - Obtiene o crea cliente en Supabase
- `update_customer_city(customer_id: str, city: str) -> Dict[str, Any]` - Actualiza ciudad del cliente
- `clear_customer_city(customer_id: Optional[str])` - Limpia ciudad del cliente
- `clear_customer_consent(customer_id: Optional[str])` - Limpia consentimiento del cliente

### Funciones de Consentimiento
- `request_consent(phone: str) -> Dict[str, Any]` - Solicita consentimiento al usuario
- `handle_consent_response(phone: str, customer_profile: Dict[str, Any], selected: str, payload: Dict[str, Any])` - Maneja respuesta de consentimiento

### Funciones de Búsqueda
- `search_providers(service: str, city: str) -> List[Dict[str, Any]]` - Busca proveedores
- `send_provider_prompt(phone: str, flow: Dict[str, Any], city: str) -> Dict[str, Any]` - Envía mensaje con lista de proveedores
- `send_confirm_prompt(phone: str, flow: Dict[str, Any], title: str) -> Dict[str, Any]` - Envía mensaje de confirmación

### Funciones de Validación
- `check_if_banned(phone: str) -> bool` - Verifica si el teléfono está baneado
- `validate_content_with_ai(text: str, phone: str) -> tuple[Optional[str], Optional[str]]` - Valida contenido con IA

### Funciones de Utilidad
- `formal_connection_message(provider: Dict[str, Any]) -> Dict[str, Any]` - Genera mensaje de conexión
- `schedule_feedback_request(phone: str, provider: Dict[str, Any])` - Agenda solicitud de feedback
- `send_whatsapp_text(phone: str, text: str) -> bool` - Envía mensaje de WhatsApp (scheduler)

### Funciones de Utilidad Normalización
- `normalize_button(val: Optional[str]) -> Optional[str]` - Normaliza valor de botón

## 4. Constantes y Configuración

Las siguientes constantes permanecen en main.py (ya están copiadas en el orquestador también):

```python
ECUADOR_CITY_SYNONYMS = { ... }
GREETINGS = { ... }
RESET_KEYWORDS = { ... }
MAX_CONFIRM_ATTEMPTS = 2
FAREWELL_MESSAGE = "..."
AFFIRMATIVE_WORDS = { ... }
NEGATIVE_WORDS = { ... }
USE_AI_EXPANSION = os.getenv("USE_AI_EXPANSION", "true").lower() == "true"
```

## 5. Arquitectura de la Solución

```
main.py (Capa HTTP + Funciones Auxiliares)
    ↓
OrquestadorConversacional (Capa de Orquestación)
    ↓
Manejadores de Estados (flows/manejadores_estados/)
    ↓
Constructores de Búsqueda (flows/busqueda_proveedores/)
    ↓
Templates de Mensajes (templates/)
```

## 6. Beneficios de la Refactorización

1. **Separación de Responsabilidades**: La capa HTTP ahora solo maneja requests/responses
2. **Testabilidad**: El orquestador puede testearse independientemente de FastAPI
3. **Mantenibilidad**: La lógica de orquestación está centralizada en un solo archivo
4. **Reutilización**: El orquestador puede usarse desde otros endpoints o servicios
5. **Claridad**: El endpoint se reduce de ~548 líneas a ~10 líneas

## 7. Pruebas

Para probar la integración:

```python
# Test de integración simple
async def test_orquestador():
    payload = {
        "from_number": "593990000000",
        "content": "hola",
        "selected_option": None,
        "message_type": "text",
        "location": None,
    }

    result = await orquestador.procesar_mensaje_whatsapp(payload)
    print(result)
```

## 8. Notas Importantes

1. **Callbacks Obligatorios**: Todos los callbacks deben inyectarse ANTES de usar el orquestador
2. **Orden de Inicialización**: El orquestador debe crearse después de inicializar todas sus dependencias
3. **Logging**: El orquestador usa `logger` proporcionado en el constructor
4. **Error Handling**: El orquestador puede lanzar `ValueError` para errores de validación
