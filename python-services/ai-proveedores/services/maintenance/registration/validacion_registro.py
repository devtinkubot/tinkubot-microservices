"""Validación local de registro para maintenance."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, cast

from models.proveedores import SolicitudCreacionProveedor
from pydantic import ValidationError
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from services.shared.ubicacion_ecuador import validar_y_normalizar_ubicacion

logger = logging.getLogger(__name__)


def validar_y_construir_proveedor(
    flujo: Dict[str, Any],
    telefono: str,
) -> Tuple[bool, Optional[str], Optional[SolicitudCreacionProveedor]]:
    especialidad = flujo.get("specialty")
    servicios_lista = _procesar_lista_servicios(especialidad)

    ciudad_cruda = flujo.get("city") or ""
    ciudad_canonica, estado_ciudad = validar_y_normalizar_ubicacion(ciudad_cruda)
    if not ciudad_canonica:
        logger.warning(
            "Ciudad inválida en flujo de registro: valor=%r estado=%s",
            ciudad_cruda,
            estado_ciudad,
        )
        return (
            False,
            "ciudad: ubicación no reconocida (usa ciudad o cantón de Ecuador)",
            None,
        )

    try:
        nombre_visible = resolver_nombre_visible_proveedor(
            proveedor=flujo,
            fallback="",
        )
        proveedor = SolicitudCreacionProveedor(
            phone=telefono,
            account_id=flujo.get("account_id"),
            from_number=flujo.get("from_number"),
            user_id=flujo.get("user_id"),
            real_phone=flujo.get("real_phone") or flujo.get("phone_user"),
            full_name=nombre_visible,
            city=ciudad_canonica,
            services_list=servicios_lista,
            service_entries=list(
                flujo.get("servicios_detallados") or flujo.get("service_entries") or []
            ),
            experience_range=flujo.get("experience_range"),
            has_consent=flujo.get("has_consent", False),
            display_name=flujo.get("display_name"),
            formatted_name=flujo.get("formatted_name"),
            first_name=flujo.get("first_name"),
            last_name=flujo.get("last_name"),
            document_first_names=flujo.get("document_first_names"),
            document_last_names=flujo.get("document_last_names"),
            document_id_number=flujo.get("document_id_number"),
            location_lat=flujo.get("location_lat"),
            location_lng=flujo.get("location_lng"),
        )
        return True, None, proveedor
    except ValidationError as exc:
        logger.error("Error de validación en datos de registro: %s", exc)
        errores = exc.errors()
        primer_error = cast(Dict[str, Any], errores[0]) if errores else {}
        mensaje_error = _formatear_mensaje_error_validacion(primer_error)
        return False, mensaje_error, None
    except Exception as exc:
        logger.error("Error inesperado al validar datos de registro: %s", exc)
        return False, "Error inesperado al validar los datos", None


def _procesar_lista_servicios(especialidad: Optional[str]) -> List[str]:
    if not especialidad or not isinstance(especialidad, str):
        return []
    servicios = [
        item.strip()
        for item in re.split(r"[;,/\n]+", especialidad)
        if item and item.strip()
    ]
    if not servicios and especialidad.strip():
        servicios = [especialidad.strip()]
    return servicios


def _formatear_mensaje_error_validacion(error: Dict[str, Any]) -> str:
    if not error:
        return "Datos inválidos"
    campo = error.get("loc", ["campo"])[0]
    mensaje = error.get("msg", "valor inválido")
    nombres_campos = {
        "phone": "teléfono",
        "real_phone": "teléfono real",
        "first_name": "nombre",
        "last_name": "apellido",
        "city": "ciudad",
        "services_list": "servicios",
        "has_consent": "consentimiento",
    }
    campo_espanol = nombres_campos.get(campo, campo)
    return f"{campo_espanol}: {mensaje}"
