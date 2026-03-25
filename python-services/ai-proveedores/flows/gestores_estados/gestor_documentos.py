"""Manejadores de estados para documentos de actualización."""

from typing import Any, Dict, Optional

from flows.constructores import (
    construir_payload_menu_principal,
)
from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from services import actualizar_documentos_identidad
from templates.interfaz import (
    confirmar_documentos_actualizados,
    error_actualizar_documentos,
    solicitar_dni_actualizacion,
)
from templates.onboarding.ciudad import solicitar_ciudad_actualizacion


def manejar_inicio_documentos(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Inicia el flujo de documentación."""
    flujo["state"] = "awaiting_city"
    return {
        "success": True,
        "messages": [solicitar_ciudad_actualizacion()],
    }


def manejar_inicio_actualizacion_documentos(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Inicia flujo post-registro de actualización de cédula."""
    flujo["state"] = "awaiting_dni_front_photo_update"
    return {
        "success": True,
        "messages": [{"response": solicitar_dni_actualizacion()}],
    }


def manejar_dni_frontal_actualizacion(
    flujo: Dict[str, Any], carga: Dict[str, Any]
) -> Dict[str, Any]:
    """Procesa foto frontal del DNI para actualización post-registro."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [payload_onboarding_dni_frontal()],
        }
    flujo["dni_front_image"] = imagen_b64
    flujo["state"] = "awaiting_menu_option"
    return {
        "success": True,
        "messages": [{"response": "__persistir_dni_frontal__"}],
    }


async def manejar_dni_trasera_actualizacion(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    proveedor_id: Optional[str],
    subir_medios_identidad,
) -> Dict[str, Any]:
    """Persiste la foto frontal del DNI en la actualización post-registro."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if imagen_b64 and not flujo.get("dni_front_image"):
        flujo["dni_front_image"] = imagen_b64
    if not flujo.get("dni_front_image"):
        return {
            "success": True,
            "messages": [{"response": payload_onboarding_dni_frontal()}],
        }
    if not proveedor_id or not subir_medios_identidad:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": error_actualizar_documentos()},
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    resultado = await actualizar_documentos_identidad(
        subir_medios_identidad,
        proveedor_id,
        flujo.get("dni_front_image"),
    )
    flujo.pop("dni_front_image", None)
    flujo.pop("profile_edit_mode", None)
    retorno_estado = str(flujo.pop("profile_return_state", "") or "").strip()
    flujo["state"] = retorno_estado or "awaiting_menu_option"

    if not resultado.get("success"):
        return {
            "success": True,
            "messages": [
                {"response": error_actualizar_documentos()},
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    if retorno_estado:
        from .gestor_vistas_perfil import render_profile_view

        return {
            "success": True,
            "messages": [
                {"response": confirmar_documentos_actualizados()},
                await render_profile_view(
                    flujo=flujo,
                    estado=retorno_estado,
                    proveedor_id=proveedor_id,
                ),
            ],
        }

    return {
        "success": True,
        "messages": [
            {"response": confirmar_documentos_actualizados()},
            construir_payload_menu_principal(
                esta_registrado=True,
                approved_basic=bool(flujo.get("approved_basic")),
            ),
        ],
    }
