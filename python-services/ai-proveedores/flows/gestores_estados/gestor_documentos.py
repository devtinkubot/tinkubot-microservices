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


def manejar_inicio_documentos(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Inicia el flujo de documentación."""
    flujo["state"] = "awaiting_city"
    return {
        "success": True,
        "response": preguntar_actualizar_ciudad(),
    }


def manejar_dni_frontal(flujo: Dict[str, Any], carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto frontal del DNI."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "response": solicitar_foto_dni_frontal(),
        }
    flujo["dni_front_image"] = imagen_b64
    flujo["state"] = "awaiting_dni_back_photo"
    return {
        "success": True,
        "response": solicitar_foto_dni_trasera(),
    }


def manejar_dni_trasera(flujo: Dict[str, Any], carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa foto trasera del DNI."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "response": solicitar_foto_dni_trasera_requerida(),
        }
    flujo["dni_back_image"] = imagen_b64
    flujo["state"] = "awaiting_face_photo"
    return {
        "success": True,
        "response": solicitar_selfie_registro(),
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
        ],
    }
