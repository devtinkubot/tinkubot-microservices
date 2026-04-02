"""Manejador del estado awaiting_menu_option."""

import logging
from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal
from services import listar_certificados_proveedor
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from templates.maintenance import solicitar_confirmacion_eliminacion
from templates.maintenance.menus import (
    MENU_ID_COMPLETAR_PERFIL,
    MENU_ID_ELIMINAR_REGISTRO,
    MENU_ID_INFO_PERSONAL,
    MENU_ID_INFO_PROFESIONAL,
    MENU_ID_SALIR,
    SUBMENU_ID_PERSONAL_DNI_FRONTAL,
    SUBMENU_ID_PERSONAL_DNI_REVERSO,
    SUBMENU_ID_PERSONAL_FOTO,
    SUBMENU_ID_PERSONAL_NOMBRE,
    SUBMENU_ID_PERSONAL_REGRESAR,
    SUBMENU_ID_PERSONAL_UBICACION,
    SUBMENU_ID_PROF_CERTIFICADOS,
    SUBMENU_ID_PROF_EXPERIENCIA,
    SUBMENU_ID_PROF_REDES,
    SUBMENU_ID_PROF_REGRESAR,
    SUBMENU_ID_PROF_SERVICIOS,
    payload_submenu_informacion_personal,
    payload_submenu_informacion_profesional,
)
from templates.maintenance.registration import (
    mensaje_inicio_perfil_profesional,
)
from templates.shared import informar_cierre_sesion

from .views import render_profile_view

# Compatibilidad para tests y monkeypatches existentes.
LISTAR_CERTIFICADOS_PROVEEDOR = listar_certificados_proveedor

logger = logging.getLogger(__name__)


def iniciar_flujo_completar_perfil_profesional(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    """Inicializa la segunda etapa del perfil profesional."""
    servicios_temporales = list(flujo.get("services") or [])
    flujo["profile_completion_mode"] = True
    flujo["servicios_temporales"] = servicios_temporales
    flujo["state"] = "maintenance_experience"
    return {
        "success": True,
        "messages": [{"response": mensaje_inicio_perfil_profesional()}],
    }


def _payload_menu_principal_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return construir_payload_menu_principal(
        esta_registrado=True,
        provider_name=resolver_nombre_visible_proveedor(proveedor=flujo),
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
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el submenú de información personal."""
    seleccion = (selected_option or "").strip().lower()

    if seleccion == SUBMENU_ID_PERSONAL_NOMBRE:
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

    if seleccion == SUBMENU_ID_PERSONAL_UBICACION:
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

    if seleccion == SUBMENU_ID_PERSONAL_FOTO:
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

    if seleccion == SUBMENU_ID_PERSONAL_DNI_FRONTAL:
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

    if seleccion == SUBMENU_ID_PERSONAL_DNI_REVERSO:
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

    if seleccion == SUBMENU_ID_PERSONAL_REGRESAR:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_payload_menu_principal_desde_flujo(flujo)],
        }

    return {
        "success": True,
        "messages": [payload_submenu_informacion_personal()],
    }


async def manejar_submenu_informacion_profesional(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el submenú de información profesional."""
    seleccion = (selected_option or "").strip().lower()

    if seleccion == SUBMENU_ID_PROF_EXPERIENCIA:
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

    if seleccion == SUBMENU_ID_PROF_SERVICIOS:
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

    if seleccion == SUBMENU_ID_PROF_CERTIFICADOS:
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

    if seleccion == SUBMENU_ID_PROF_REDES:
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

    if seleccion == SUBMENU_ID_PROF_REGRESAR:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_payload_menu_principal_desde_flujo(flujo)],
        }

    return {
        "success": True,
        "messages": [payload_submenu_informacion_profesional()],
    }


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    supabase: Any = None,
    telefono: Optional[str] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el menú principal y devuelve la respuesta."""
    logger.info(
        "🎯 manejar_estado_menu llamado. esta_registrado=%s, opcion_menu=%s, "
        "texto_mensaje='%s'",
        esta_registrado,
        opcion_menu,
        texto_mensaje,
    )
    seleccion = (selected_option or "").strip().lower()
    servicios_actuales = flujo.get("services") or []
    if seleccion == MENU_ID_COMPLETAR_PERFIL:
        return iniciar_flujo_completar_perfil_profesional(flujo)
    if seleccion == MENU_ID_INFO_PERSONAL:
        flujo["state"] = "awaiting_personal_info_action"
        return {
            "success": True,
            "messages": [payload_submenu_informacion_personal()],
        }

    if seleccion == MENU_ID_INFO_PROFESIONAL:
        flujo["state"] = "awaiting_professional_info_action"
        return {
            "success": True,
            "messages": [payload_submenu_informacion_profesional()],
        }

    if seleccion == MENU_ID_ELIMINAR_REGISTRO:
        flujo["state"] = "awaiting_deletion_confirmation"
        return {
            "success": True,
            "messages": [{"response": solicitar_confirmacion_eliminacion()}],
        }
    if seleccion == MENU_ID_SALIR:
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
        "messages": [_payload_menu_principal_desde_flujo(flujo)],
    }
