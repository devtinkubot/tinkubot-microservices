"""Manejadores de estados para documentos de registro y actualización."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal, construir_resumen_confirmacion
from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from services import actualizar_documentos_identidad
from templates.interfaz import (
    confirmar_documentos_actualizados,
    error_actualizar_documentos,
    solicitar_dni_actualizacion,
)
from templates.registro import (
    solicitar_ciudad_actualizacion,
    pedir_confirmacion_resumen,
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)
from templates.registro import informar_datos_recibidos


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


def manejar_dni_frontal(flujo: Dict[str, Any], carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto frontal del DNI."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [{"response": solicitar_foto_dni_frontal()}],
        }
    flujo["dni_front_image"] = imagen_b64
    flujo["state"] = "awaiting_dni_back_photo"
    return {
        "success": True,
        "messages": [{"response": solicitar_foto_dni_trasera()}],
    }


def manejar_dni_trasera(flujo: Dict[str, Any], carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto trasera del DNI."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [{"response": solicitar_foto_dni_trasera_requerida()}],
        }
    flujo["dni_back_image"] = imagen_b64
    flujo["state"] = "awaiting_face_photo"
    return {
        "success": True,
        "messages": [{"response": solicitar_selfie_registro()}],
    }


def manejar_dni_frontal_actualizacion(
    flujo: Dict[str, Any], carga: Dict[str, Any]
) -> Dict[str, Any]:
    """Procesa foto frontal del DNI para actualización post-registro."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [{"response": solicitar_foto_dni_frontal()}],
        }
    flujo["dni_front_image"] = imagen_b64
    flujo["state"] = "awaiting_dni_back_photo_update"
    return {
        "success": True,
        "messages": [{"response": solicitar_foto_dni_trasera()}],
    }


async def manejar_dni_trasera_actualizacion(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    proveedor_id: Optional[str],
    subir_medios_identidad,
) -> Dict[str, Any]:
    """Procesa foto trasera del DNI y persiste actualización post-registro."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [{"response": solicitar_foto_dni_trasera_requerida()}],
        }

    flujo["dni_back_image"] = imagen_b64
    if not proveedor_id or not subir_medios_identidad:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": error_actualizar_documentos()},
                {
                    "response": construir_menu_principal(
                        esta_registrado=True,
                        menu_limitado=bool(flujo.get("menu_limitado")),
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    resultado = await actualizar_documentos_identidad(
        subir_medios_identidad,
        proveedor_id,
        flujo.get("dni_front_image"),
        flujo.get("dni_back_image"),
    )
    flujo.pop("dni_front_image", None)
    flujo.pop("dni_back_image", None)
    flujo["state"] = "awaiting_menu_option"

    if not resultado.get("success"):
        return {
            "success": True,
            "messages": [
                {"response": error_actualizar_documentos()},
                {
                    "response": construir_menu_principal(
                        esta_registrado=True,
                        menu_limitado=bool(flujo.get("menu_limitado")),
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    return {
        "success": True,
        "messages": [
            {"response": confirmar_documentos_actualizados()},
            {
                "response": construir_menu_principal(
                    esta_registrado=True,
                    menu_limitado=bool(flujo.get("menu_limitado")),
                    approved_basic=bool(flujo.get("approved_basic")),
                )
            },
        ],
    }


def manejar_selfie_registro(flujo: Dict[str, Any], carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa selfie del registro."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "response": solicitar_selfie_requerida_registro(),
        }
    flujo["face_image"] = imagen_b64
    resumen = construir_resumen_confirmacion(flujo)
    flujo["state"] = "confirm"
    return {
        "success": True,
        "messages": [
            {"response": informar_datos_recibidos()},
            {"response": resumen},
            {"response": pedir_confirmacion_resumen()},
        ],
    }
