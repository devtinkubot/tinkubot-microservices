"""Manejador del estado awaiting_menu_option."""

import logging
from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from templates.registro import (
    mensaje_resumen_servicios_registro,
    preguntar_siguiente_servicio_registro,
)
from templates.interfaz import (
    error_opcion_no_reconocida,
    informar_cierre_sesion,
    solicitar_confirmacion_eliminacion,
    solicitar_dni_actualizacion,
    solicitar_red_social_actualizacion,
    solicitar_selfie_actualizacion,
)
from templates.registro import (
    PROMPT_INICIO_REGISTRO,
    preguntar_real_phone,
    solicitar_ciudad_registro,
)

logger = logging.getLogger(__name__)


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    menu_limitado: bool = False,
) -> Dict[str, Any]:
    """Procesa el menú principal y devuelve la respuesta."""
    logger.info(
        "🎯 manejar_estado_menu llamado. esta_registrado=%s, opcion_menu=%s, "
        "texto_mensaje='%s'",
        esta_registrado,
        opcion_menu,
        texto_mensaje,
    )
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()
    approved_basic = bool(flujo.get("approved_basic"))
    max_opcion_menu = 1 if approved_basic else 5

    if not esta_registrado:
        if opcion == "1" or "registro" in texto_minusculas:
            logger.info(
                "✅ Usuario NO registrado seleccionó Registro. "
                "Cambiando estado a awaiting_city"
            )
            logger.info("📤 Respuesta a devolver: '%s'", PROMPT_INICIO_REGISTRO)
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
            logger.info("📦 Response completo: %s", respuesta)
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
    if approved_basic:
        if opcion == "1" or "completar perfil" in texto_minusculas:
            servicios_temporales = list(servicios_actuales)
            flujo["profile_completion_mode"] = True
            flujo["servicios_temporales"] = servicios_temporales
            if servicios_temporales:
                flujo["state"] = "awaiting_services_confirmation"
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "Vamos a completar tu perfil profesional. "
                                "Revisa tus servicios actuales y confirma o corrige antes de continuar."
                            )
                        },
                        {
                            "response": mensaje_resumen_servicios_registro(
                                servicios_temporales,
                                SERVICIOS_MAXIMOS,
                            )
                        },
                    ],
                }
            flujo["state"] = "awaiting_specialty"
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Vamos a completar tu perfil profesional.\n\n"
                            + preguntar_siguiente_servicio_registro(1, SERVICIOS_MAXIMOS)
                        )
                    }
                ],
            }

        return {
            "success": True,
            "messages": [
                {"response": error_opcion_no_reconocida(1, 1)},
                {
                    "response": construir_menu_principal(
                        esta_registrado=True,
                        approved_basic=True,
                    )
                },
            ],
        }

    if "completar perfil" in texto_minusculas or "perfil profesional" in texto_minusculas:
        servicios_temporales = list(servicios_actuales)
        flujo["profile_completion_mode"] = True
        flujo["servicios_temporales"] = servicios_temporales
        if servicios_temporales:
            flujo["state"] = "awaiting_services_confirmation"
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Vamos a completar tu perfil profesional. "
                            "Revisa tus servicios actuales y confirma o corrige antes de continuar."
                        )
                    },
                    {
                        "response": mensaje_resumen_servicios_registro(
                            servicios_temporales,
                            SERVICIOS_MAXIMOS,
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Vamos a completar tu perfil profesional.\n\n"
                        + preguntar_siguiente_servicio_registro(1, SERVICIOS_MAXIMOS)
                    )
                }
            ],
        }

    if opcion == "1" or "servicio" in texto_minusculas:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {
                    "response": construir_menu_servicios(
                        servicios_actuales,
                        SERVICIOS_MAXIMOS,
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
        opcion == "4"
        or "cedula" in texto_minusculas
        or "cédula" in texto_minusculas
        or "dni" in texto_minusculas
    ):
        flujo["state"] = "awaiting_dni_front_photo_update"
        return {
            "success": True,
            "messages": [{"response": solicitar_dni_actualizacion()}],
        }

    if not menu_limitado and (
        opcion == "4"
        or "eliminar" in texto_minusculas
        or "borrar" in texto_minusculas
        or "delete" in texto_minusculas
    ):
        flujo["state"] = "awaiting_deletion_confirmation"
        return {
            "success": True,
            "messages": [{"response": solicitar_confirmacion_eliminacion()}],
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
            "approved_basic": approved_basic,
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
                    approved_basic=approved_basic,
                )
            },
        ],
    }
