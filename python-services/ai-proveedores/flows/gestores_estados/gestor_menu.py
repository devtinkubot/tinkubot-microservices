"""Manejador del estado awaiting_menu_option."""

import logging
from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios

logger = logging.getLogger(__name__)
from templates.registro import PROMPT_INICIO_REGISTRO, preguntar_real_phone
from templates.interfaz import (
    error_opcion_no_reconocida,
    informar_cierre_sesion,
    solicitar_selfie_actualizacion,
    solicitar_red_social_actualizacion,
    solicitar_confirmacion_eliminacion,
)
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
) -> Dict[str, Any]:
    """Procesa el menú principal y devuelve la respuesta."""
    logger.info(f"🎯 manejar_estado_menu llamado. esta_registrado={esta_registrado}, opcion_menu={opcion_menu}, texto_mensaje='{texto_mensaje}'")
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()

    if not esta_registrado:
        if opcion == "1" or "registro" in texto_minusculas:
            logger.info(f"✅ Usuario NO registrado seleccionó Registro. Cambiando estado a awaiting_city")
            logger.info(f"📤 Respuesta a devolver: '{PROMPT_INICIO_REGISTRO}'")
            flujo["mode"] = "registration"
            if flujo.get("requires_real_phone"):
                flujo["state"] = "awaiting_real_phone"
                respuesta = {
                    "success": True,
                    "messages": [{"response": preguntar_real_phone()}],
                }
            else:
                flujo["state"] = "awaiting_city"
                respuesta = {
                    "success": True,
                    "messages": [{"response": PROMPT_INICIO_REGISTRO}],
                }
            logger.info(f"📦 Response completo: {respuesta}")
            return respuesta
        if opcion == "2" or "salir" in texto_minusculas:
            flujo.clear()
            flujo["has_consent"] = True
            return {
                "success": True,
                "messages": [{"response": informar_cierre_sesion()}],
            }

        return {
            "success": True,
            "messages": [
                {"response": error_opcion_no_reconocida(1, 2)},
                {"response": construir_menu_principal(esta_registrado=False)},
            ],
        }

    servicios_actuales = flujo.get("services") or []
    if opcion == "1" or "servicio" in texto_minusculas:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)}
            ],
        }
    if opcion == "2" or "selfie" in texto_minusculas or "foto" in texto_minusculas:
        flujo["state"] = "awaiting_face_photo_update"
        return {
            "success": True,
            "messages": [{"response": solicitar_selfie_actualizacion()}],
        }
    if (
        opcion == "3"
        or "red" in texto_minusculas
        or "social" in texto_minusculas
        or "instagram" in texto_minusculas
    ):
        flujo["state"] = "awaiting_social_media_update"
        return {
            "success": True,
            "messages": [{"response": solicitar_red_social_actualizacion()}],
        }
    if (
        opcion == "4"
        or "eliminar" in texto_minusculas
        or "borrar" in texto_minusculas
        or "delete" in texto_minusculas
    ):
        flujo["state"] = "awaiting_deletion_confirmation"
        return {
            "success": True,
            "messages": [
                {"response": solicitar_confirmacion_eliminacion()},
            ],
        }
    if opcion == "5" or "salir" in texto_minusculas or "volver" in texto_minusculas:
        flujo_base = {
            "has_consent": True,
            "esta_registrado": True,
            "provider_id": flujo.get("provider_id"),
            "services": servicios_actuales,
        }
        flujo.clear()
        flujo.update(flujo_base)
        return {
            "success": True,
            "messages": [{"response": informar_cierre_sesion()}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 5)},
            {"response": construir_menu_principal(esta_registrado=True)},
        ],
    }
