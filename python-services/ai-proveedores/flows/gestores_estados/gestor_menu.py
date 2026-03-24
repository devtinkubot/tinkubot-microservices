"""Manejador del estado awaiting_menu_option."""

import logging
from typing import Any, Dict, Optional

from flows.constructores import (
    construir_menu_servicios,
    construir_payload_menu_principal,
)
from services import asegurar_proveedor_borrador, listar_certificados_proveedor
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from .gestor_vistas_perfil import render_profile_view
from templates.registro import (
    mensaje_inicio_perfil_profesional,
    payload_certificado_opcional,
)
from templates.onboarding.inicio import ONBOARDING_REGISTER_BUTTON_ID
from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.interfaz import (
    MENU_ID_ELIMINAR_REGISTRO,
    MENU_ID_INFO_PERSONAL,
    MENU_ID_INFO_PROFESIONAL,
    MENU_ID_SALIR,
    payload_submenu_informacion_personal,
    payload_submenu_informacion_profesional,
    error_opcion_no_reconocida,
    informar_cierre_sesion,
    solicitar_confirmacion_eliminacion,
    solicitar_dni_actualizacion,
    SUBMENU_ID_PERSONAL_DOCUMENTOS,
    SUBMENU_ID_PERSONAL_DNI_FRONTAL,
    SUBMENU_ID_PERSONAL_DNI_REVERSO,
    SUBMENU_ID_PERSONAL_FOTO,
    SUBMENU_ID_PERSONAL_NOMBRE,
    SUBMENU_ID_PERSONAL_REGRESAR,
    SUBMENU_ID_PERSONAL_UBICACION,
    SUBMENU_ID_PROF_CERTIFICADOS,
    SUBMENU_ID_PROF_EXPERIENCIA,
    SUBMENU_ID_PROF_REGRESAR,
    SUBMENU_ID_PROF_REDES,
    SUBMENU_ID_PROF_SERVICIOS,
)
logger = logging.getLogger(__name__)


def iniciar_flujo_completar_perfil_profesional(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    """Inicializa la segunda etapa del perfil profesional."""
    servicios_temporales = list(flujo.get("services") or [])
    flujo["profile_completion_mode"] = True
    flujo["servicios_temporales"] = servicios_temporales
    flujo["state"] = "awaiting_experience"
    return {
        "success": True,
        "messages": [{"response": mensaje_inicio_perfil_profesional()}],
    }


def _payload_menu_principal_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return construir_payload_menu_principal(
        esta_registrado=True,
        menu_limitado=bool(flujo.get("menu_limitado")),
        approved_basic=bool(flujo.get("approved_basic")),
        provider_name=str(flujo.get("full_name") or flujo.get("name") or ""),
    )


def _es_opcion_info_personal(texto: str, opcion: Optional[str]) -> bool:
    return (
        opcion == "1"
        or texto == MENU_ID_INFO_PERSONAL
        or "informacion personal" in texto
        or "información personal" in texto
    )


def _es_opcion_info_profesional(texto: str, opcion: Optional[str]) -> bool:
    return (
        opcion == "2"
        or texto == MENU_ID_INFO_PROFESIONAL
        or "informacion profesional" in texto
        or "información profesional" in texto
    )


async def manejar_submenu_informacion_personal(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Procesa el submenú de información personal."""
    texto = (texto_mensaje or "").strip().lower()

    if (
        opcion_menu == "1"
        or texto == SUBMENU_ID_PERSONAL_NOMBRE
        or "nombre" in texto
    ):
        flujo["state"] = "viewing_personal_name"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_personal_name",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "2"
        or texto == SUBMENU_ID_PERSONAL_UBICACION
        or "ubicacion" in texto
        or "ubicación" in texto
        or "ciudad" in texto
    ):
        flujo["state"] = "viewing_personal_city"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_personal_city",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "3"
        or texto == SUBMENU_ID_PERSONAL_FOTO
        or "foto" in texto
        or "selfie" in texto
    ):
        flujo["state"] = "viewing_personal_photo"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_personal_photo",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "4"
        or texto == SUBMENU_ID_PERSONAL_DNI_FRONTAL
        or "frontal" in texto
    ):
        flujo["state"] = "viewing_personal_dni_front"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_personal_dni_front",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "5"
        or texto == SUBMENU_ID_PERSONAL_DNI_REVERSO
        or "reverso" in texto
        or "posterior" in texto
    ):
        flujo["state"] = "viewing_personal_dni_back"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_personal_dni_back",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if texto == SUBMENU_ID_PERSONAL_REGRESAR or "menu" in texto or "volver" in texto or "salir" in texto:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_payload_menu_principal_desde_flujo(flujo)],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 5)},
            payload_submenu_informacion_personal(),
        ],
    }


async def manejar_submenu_informacion_profesional(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Procesa el submenú de información profesional."""
    texto = (texto_mensaje or "").strip().lower()

    if (
        opcion_menu == "1"
        or texto == SUBMENU_ID_PROF_EXPERIENCIA
        or "experiencia" in texto
    ):
        flujo["state"] = "viewing_professional_experience"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_experience",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "2"
        or texto == SUBMENU_ID_PROF_SERVICIOS
        or "servicio" in texto
    ):
        flujo["state"] = "viewing_professional_services"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_services",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "3"
        or texto == SUBMENU_ID_PROF_CERTIFICADOS
        or "certificado" in texto
    ):
        flujo["state"] = "viewing_professional_certificates"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_certificates",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if (
        opcion_menu == "4"
        or texto == SUBMENU_ID_PROF_REDES
        or "red" in texto
        or "social" in texto
        or "instagram" in texto
    ):
        flujo["state"] = "viewing_professional_social"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_social",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if texto == SUBMENU_ID_PROF_REGRESAR or "menu" in texto or "volver" in texto or "salir" in texto:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_payload_menu_principal_desde_flujo(flujo)],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 5)},
            payload_submenu_informacion_profesional(),
        ],
    }


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    menu_limitado: bool = False,
    supabase: Any = None,
    telefono: Optional[str] = None,
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
    max_opcion_menu = 5 if menu_limitado else 4

    if not esta_registrado:
        if (
            opcion == "1"
            or opcion == ONBOARDING_REGISTER_BUTTON_ID
            or "registro" in texto_minusculas
            or "registrarse" in texto_minusculas
        ):
            logger.info(
                "✅ Usuario NO registrado seleccionó Registro. "
                "Cambiando estado a awaiting_city"
            )
            logger.info(
                "📤 Respuesta a devolver: '%s'",
                solicitar_ciudad_registro()["response"],
            )
            flujo["mode"] = "registration"
            borrador = None
            if supabase and telefono:
                borrador = await asegurar_proveedor_borrador(
                    supabase=supabase,
                    telefono=telefono,
                )
            if borrador and borrador.get("id"):
                flujo["provider_id"] = str(borrador.get("id") or "").strip()
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
                construir_payload_menu_principal(esta_registrado=False),
            ],
        }

    servicios_actuales = flujo.get("services") or []
    if "completar perfil" in texto_minusculas or "perfil profesional" in texto_minusculas:
        return iniciar_flujo_completar_perfil_profesional(flujo)
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

    if not menu_limitado and _es_opcion_info_personal(texto_minusculas, opcion):
        flujo["state"] = "awaiting_personal_info_action"
        return {
            "success": True,
            "messages": [payload_submenu_informacion_personal()],
        }

    if not menu_limitado and _es_opcion_info_profesional(texto_minusculas, opcion):
        flujo["state"] = "awaiting_professional_info_action"
        return {
            "success": True,
            "messages": [payload_submenu_informacion_profesional()],
        }

    if not menu_limitado and (
        opcion == "3"
        or texto_minusculas == MENU_ID_ELIMINAR_REGISTRO
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
        opcion == "4"
        or texto_minusculas == MENU_ID_SALIR
        or opcion == str(max_opcion_menu)
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
            _payload_menu_principal_desde_flujo(flujo),
        ],
    }
