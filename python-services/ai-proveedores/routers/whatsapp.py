import logging
from time import perf_counter
from typing import Any, Dict

from config import configuracion
from dependencies import deps
from fastapi import APIRouter
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp
from services.shared.orquestacion_whatsapp import (
    procesar_mensaje_whatsapp,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    solicitud: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    inicio_tiempo = perf_counter()
    try:
        return await procesar_mensaje_whatsapp(
            solicitud=solicitud,
            supabase=deps.supabase,
            servicio_embeddings=deps.servicio_embeddings,
            cliente_openai=deps.cliente_openai,
            logger=logger,
            subir_medios_identidad_fn=subir_medios_identidad,
        )

    except Exception as error:
        import traceback

        logger.error(
            f"❌ Error procesando mensaje WhatsApp: {error}\n{traceback.format_exc()}"
        )
        return {"success": False, "message": f"Error procesando mensaje: {str(error)}"}
    finally:
        ms_transcurridos = (perf_counter() - inicio_tiempo) * 1000
        if ms_transcurridos >= configuracion.slow_query_threshold_ms:
            logger.info(
                "perf_handler_whatsapp",
                extra={
                    "elapsed_ms": round(ms_transcurridos, 2),
                    "threshold_ms": configuracion.slow_query_threshold_ms,
                },
            )
