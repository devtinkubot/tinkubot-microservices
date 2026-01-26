"""
EJEMPLO DE INTEGRACIÓN DE SERVICIOS EN main.py

Este archivo muestra EXACTAMENTE cómo integrar los nuevos servicios
en el startup_event de main.py.
"""

# ============================================================================
# PASO 1: Agregar imports al inicio de main.py
# ============================================================================

from services.buscador import BuscadorProveedores
from services.validacion import ValidadorProveedoresIA
from services.expansion import ExpansorSinonimos

# ============================================================================
# PASO 2: Crear instancias de servicios DESPUÉS de inicializar OpenAI
# ============================================================================

# ... después de la línea 135 (openai_semaphore = ...) ...

# Crear servicios de dominio
expansor_servicios = ExpansorSinonimos(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger,
)

validador_proveedores = ValidadorProveedoresIA(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger,
)

buscador_proveedores = BuscadorProveedores(
    search_client=search_client,
    ai_validator=validador_proveedores,
    logger=logger,
)

logger.info("✅ Servicios de dominio inicializados")

# ============================================================================
# PASO 3: Reemplazar funciones en callbacks del orquestador
# ============================================================================

# En startup_event(), alrededor de línea 1758, reemplazar:

# ANTES (código actual):
orquestador.inyectar_callbacks(
    # ... otros callbacks ...
    search_providers=search_providers,  # ❌ Función global
    # ... otros callbacks ...
)

# DESPUÉS (nuevo código):
orquestador.inyectar_callbacks(
    # ... otros callbacks ...
    search_providers=buscador_proveedores.buscar,  # ✅ Método del servicio
    # ... otros callbacks ...
)

# ============================================================================
# PASO 4: Opcional - Actualizar orquestador_conversacion.py
# ============================================================================

# Si orquestador_conversacion.py necesita expand_need_with_ai o
# extract_profession_and_location_with_expansion, actualizar:

# ANTES:
# from main import expand_need_with_ai, extract_profession_and_location_with_expansion

# DESPUÉS:
# from services.expansion import ExpansorSinonimos
# expansor = ExpansorSinonimos(...)  # Inyectar por constructor
# Usar: await expansor.expandir_necesidad_con_ia(...)

# ============================================================================
# PASO 5: Opcional - Marcar funciones antiguas como DEPRECATED
# ============================================================================

# Marcar las funciones globales como deprecated pero mantenerlas
# durante un periodo de transición:

# async def search_providers(...):
#     """DEPRECATED: Usar BuscadorProveedores.buscar() en su lugar."""
#     logger.warning("⚠️ search_providers() está DEPRECATED, usar buscador.buscar()")
#     return await buscador_proveedores.buscar(...)

# ============================================================================
# EJEMPLO COMPLETO: startup_event actualizado
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    await coordinador_disponibilidad.start_listener()

    # Crear servicios de dominio (NUEVO)
    expansor_servicios = ExpansorSinonimos(
        openai_client=openai_client,
        openai_semaphore=openai_semaphore,
        openai_timeout=OPENAI_TIMEOUT_SECONDS,
        logger=logger,
    )

    validador_proveedores = ValidadorProveedoresIA(
        openai_client=openai_client,
        openai_semaphore=openai_semaphore,
        openai_timeout=OPENAI_TIMEOUT_SECONDS,
        logger=logger,
    )

    buscador_proveedores = BuscadorProveedores(
        search_client=search_client,
        ai_validator=validador_proveedores,
        logger=logger,
    )

    logger.info("✅ Servicios de dominio inicializados")

    # Inyectar callbacks del orquestador (ACTUALIZADO)
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
        search_providers=buscador_proveedores.buscar,  # ✅ NUEVO
        send_provider_prompt=send_provider_prompt,
        send_confirm_prompt=send_confirm_prompt,
        clear_customer_city=clear_customer_city,
        clear_customer_consent=clear_customer_consent,
        formal_connection_message=formal_connection_message,
        schedule_feedback_request=schedule_feedback_request,
        send_whatsapp_text=send_whatsapp_text,
    )
    logger.info("✅ AI Service Clientes listo")

# ============================================================================
# PASO 6: Verificación
# ============================================================================

# Después de integrar, verificar que todo funciona:

# 1. Reiniciar el servicio:
#    docker-compose restart ai-clientes
#    o
#    uvicorn main:app --reload

# 2. Revisar logs para confirmar inicialización:
#    Deberías ver: "✅ Servicios de dominio inicializados"

# 3. Probar búsqueda de proveedores
#    Debería funcionar exactamente igual que antes

# 4. Verificar que no hay errores en los logs
#    Buscar: "❌ Error" o traceback

# ============================================================================
# MAPA DE FUNCIONES → SERVICIOS
# ============================================================================

"""
Función global                    → Servicio de dominio
─────────────────────────────────────────────────────────────────────
search_providers()               → BuscadorProveedores.buscar()
ai_validate_providers()          → ValidadorProveedoresIA.validar_proveedores()
expand_need_with_ai()            → ExpansorSinonimos.expandir_necesidad_con_ia()
extract_profession_and_location() → ExpansorSinonimos.extraer_profesion_y_ubicacion()
extract_profession_and_location_with_expansion()
                                → ExpansorSinonimos.extraer_profesion_y_ubicacion_con_expansion()
_extract_profession_with_ai()    → ExpansorSinonimos._extraer_profesion_con_ia()
_extract_location_with_ai()      → ExpansorSinonimos._extraer_ubicacion_con_ia()
"""

# ============================================================================
# PASO 7: Limpieza final (opcional, después de verificar que funciona)
# ============================================================================

# Una vez verificado que todo funciona, puedes eliminar las funciones globales:
# - Líneas 1039-1118: search_providers()
# - Líneas 1120-1283: ai_validate_providers()
# - Líneas 537-648: expand_need_with_ai()
# - Líneas 493-534: extract_profession_and_location()
# - Líneas 650-697: extract_profession_and_location_with_expansion()
# - Líneas 699-758: _extract_profession_with_ai()
# - Líneas 760-826: _extract_location_with_ai()

# Esto reducirá main.py de 1959 líneas a ~1550 líneas (~400 líneas menos)
