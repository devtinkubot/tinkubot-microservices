"""Manejadores de estados para documentos de registro."""

from typing import Any, Dict

from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from templates.registro import (
    preguntar_actualizar_ciudad,
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)
from flows.constructores import construir_resumen_confirmacion
from templates.registro import informar_datos_recibidos


def manejar_inicio_documentos(flow: Dict[str, Any]) -> Dict[str, Any]:
    """Inicia el flujo de documentación."""
    flow["state"] = "awaiting_city"
    return {
        "success": True,
        "response": preguntar_actualizar_ciudad(),
    }


def manejar_dni_frontal(flow: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto frontal del DNI."""
    image_b64 = extraer_primera_imagen_base64(payload)
    if not image_b64:
        return {
            "success": True,
            "response": solicitar_foto_dni_frontal(),
        }
    flow["dni_front_image"] = image_b64
    flow["state"] = "awaiting_dni_back_photo"
    return {
        "success": True,
        "response": solicitar_foto_dni_trasera(),
    }


def manejar_dni_trasera(flow: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto trasera del DNI."""
    image_b64 = extraer_primera_imagen_base64(payload)
    if not image_b64:
        return {
            "success": True,
            "response": solicitar_foto_dni_trasera_requerida(),
        }
    flow["dni_back_image"] = image_b64
    flow["state"] = "awaiting_face_photo"
    return {
        "success": True,
        "response": solicitar_selfie_registro(),
    }


def manejar_selfie_registro(flow: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa selfie del registro."""
    image_b64 = extraer_primera_imagen_base64(payload)
    if not image_b64:
        return {
            "success": True,
            "response": solicitar_selfie_requerida_registro(),
        }
    flow["face_image"] = image_b64
    summary = construir_resumen_confirmacion(flow)
    flow["state"] = "confirm"
    return {
        "success": True,
        "messages": [
            {"response": informar_datos_recibidos()},
            {"response": summary},
        ],
    }
