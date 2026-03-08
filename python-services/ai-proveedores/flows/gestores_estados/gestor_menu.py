"""Manejador del estado awaiting_menu_option."""

import logging
from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios

logger = logging.getLogger(__name__)
from templates.registro import (
    preguntar_real_phone,
    solicitar_ciudad_registro,
)
from templates.interfaz import (
    error_opcion_no_reconocida,
    informar_cierre_sesion,
    solicitar_dni_actualizacion,
    solicitar_selfie_actualizacion,
    solicitar_red_social_actualizacion,
    solicitar_confirmacion_eliminacion,
)
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS


def _servicios_pendientes_genericos(flujo: Dict[str, Any]) -> list[str]:
    return [
        servicio.strip()
        for servicio in (flujo.get("generic_services_removed") or [])
        if str(servicio or "").strip()
    ]


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    menu_limitado: bool = False,
) -> Dict[str, Any]:
    """Procesa el menú principal y devuelve la respuesta."""
    logger.info(f"🎯 manejar_estado_menu llamado. esta_registrado={esta_registrado}, opcion_menu={opcion_menu}, texto_mensaje='{texto_mensaje}'")
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()
    max_opcion_menu = 5

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
                    "messages": [solicitar_ciudad_registro()],
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
    servicios_pendientes = _servicios_pendientes_genericos(flujo)
    if opcion == "1" or "servicio" in texto_minusculas:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {
                    "response": construir_menu_servicios(
                        servicios_actuales,
                        SERVICIOS_MAXIMOS,
                        servicios_pendientes_genericos=servicios_pendientes,
                    )
                }
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
    if menu_limitado and (
        opcion == "4" or "cedula" in texto_minusculas or "cédula" in texto_minusculas or "dni" in texto_minusculas
    ):
        flujo["state"] = "awaiting_dni_front_photo_update"
        return {
            "success": True,
            "messages": [{"response": solicitar_dni_actualizacion()}],
        }

    if (
        not menu_limitado
        and (
            opcion == "4"
            or "eliminar" in texto_minusculas
            or "borrar" in texto_minusculas
            or "delete" in texto_minusculas
        )
    ):
        flujo["state"] = "awaiting_deletion_confirmation"
        return {
            "success": True,
            "messages": [
                {"response": solicitar_confirmacion_eliminacion()},
            ],
        }
    if (
        opcion == str(max_opcion_menu)
        or "salir" in texto_minusculas
        or "volver" in texto_minusculas
    ):
        flujo_base = {
            "has_consent": True,
            "esta_registrado": True,
            "provider_id": flujo.get("provider_id"),
            "services": servicios_actuales,
            "menu_limitado": menu_limitado,
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
            {"response": error_opcion_no_reconocida(1, max_opcion_menu)},
            {
                "response": construir_menu_principal(
                    esta_registrado=True,
                    menu_limitado=menu_limitado,
                )
            },
        ],
    }
