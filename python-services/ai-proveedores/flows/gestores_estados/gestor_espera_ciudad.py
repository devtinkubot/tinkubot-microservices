"""Manejador del estado awaiting_city."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from services.registro.parser_ubicacion import (
    VALIDATION_ERROR_INVALID_CHARS,
    VALIDATION_ERROR_MULTIPLE,
    VALIDATION_ERROR_TOO_LONG,
    VALIDATION_ERROR_TOO_SHORT,
    validar_y_normalizar_ubicacion,
)
from infrastructure.database import run_supabase
from flows.constructores import construir_payload_menu_principal
from services.servicios_proveedor.utilidades import limpiar_espacios
from templates.registro import (
    error_ciudad_caracteres_invalidos,
    error_ciudad_corta,
    error_ciudad_larga,
    error_ciudad_multiple,
    error_ciudad_no_reconocida,
    mensaje_error_resolviendo_ubicacion,
    preguntar_nombre,
    solicitar_ciudad_registro,
)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "tinkubot-ai-proveedores/1.0 (support@tinkubot.com)"


def _parsear_coordenada(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _normalizar_ciudad_desde_texto(texto: Optional[str]) -> Optional[str]:
    canonica, estado = validar_y_normalizar_ubicacion(limpiar_espacios(texto))
    if estado == "ok" and canonica:
        return canonica
    return None


def _extraer_ciudad_desde_payload_ubicacion(
    ubicacion: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not isinstance(ubicacion, dict):
        return None
    for campo in ("city", "address", "name"):
        ciudad = _normalizar_ciudad_desde_texto(ubicacion.get(campo))
        if ciudad:
            return ciudad
    return None


async def _resolver_ciudad_desde_coordenadas(
    latitud: float, longitud: float
) -> Optional[str]:
    params = {
        "format": "jsonv2",
        "lat": latitud,
        "lon": longitud,
        "zoom": 10,
        "addressdetails": 1,
        "accept-language": "es",
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    timeout = httpx.Timeout(2.5)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            respuesta = await client.get(
                NOMINATIM_REVERSE_URL,
                params=params,
                headers=headers,
            )
        if respuesta.status_code != 200:
            return None
        payload = respuesta.json()
        direccion = payload.get("address") or {}
        for campo in ("city", "town", "village", "municipality", "county"):
            ciudad = _normalizar_ciudad_desde_texto(direccion.get(campo))
            if ciudad:
                return ciudad
        return _normalizar_ciudad_desde_texto(payload.get("display_name"))
    except Exception:
        return None


async def _persistir_ubicacion_proveedor(
    supabase: Any,
    proveedor_id: Optional[str],
    *,
    ciudad: Optional[str] = None,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None,
) -> None:
    if not supabase or not proveedor_id:
        return
    datos_actualizacion: Dict[str, Any] = {}
    if ciudad:
        datos_actualizacion["city"] = ciudad
        datos_actualizacion["city_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    if latitud is not None:
        datos_actualizacion["location_lat"] = latitud
    if longitud is not None:
        datos_actualizacion["location_lng"] = longitud
    if latitud is not None or longitud is not None:
        datos_actualizacion["location_updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()
    if not datos_actualizacion:
        return
    await run_supabase(
        lambda: supabase.table("providers")
        .update(datos_actualizacion)
        .eq("id", proveedor_id)
        .execute(),
        label="providers.update_location_city",
    )


async def manejar_espera_ciudad(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    carga: Optional[Dict[str, Any]] = None,
    supabase: Any = None,
    proveedor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Procesa la entrada del usuario para el campo ciudad.

    Validaciones:
    - Solo UNA ubicación principal (ciudad o cantón)
    - Longitud y caracteres permitidos
    - Autocorrección de entradas compuestas (ej: "Cuenca, Azuay, Ecuador" -> "Cuenca")
    - Rechazo de ubicaciones no reconocidas

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la ciudad.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    ciudad = limpiar_espacios(texto_mensaje)
    ubicacion = (carga or {}).get("location") or {}
    latitud = _parsear_coordenada((ubicacion or {}).get("latitude"))
    longitud = _parsear_coordenada((ubicacion or {}).get("longitude"))
    ciudad_desde_payload = _extraer_ciudad_desde_payload_ubicacion(ubicacion)
    ciudad_resuelta = ciudad_desde_payload
    if (
        not ciudad_resuelta
        and latitud is not None
        and longitud is not None
    ):
        ciudad_resuelta = await _resolver_ciudad_desde_coordenadas(latitud, longitud)

    if latitud is not None:
        flujo["location_lat"] = latitud
    if longitud is not None:
        flujo["location_lng"] = longitud
    if latitud is not None or longitud is not None:
        flujo["location_updated_at"] = datetime.now(timezone.utc).isoformat()
    if proveedor_id and (latitud is not None or longitud is not None):
        try:
            await _persistir_ubicacion_proveedor(
                supabase,
                proveedor_id,
                latitud=latitud,
                longitud=longitud,
            )
        except Exception:
            pass

    if not ciudad and ciudad_resuelta:
        ciudad = ciudad_resuelta

    if not ciudad:
        if latitud is not None and longitud is not None:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_error_resolviendo_ubicacion()},
                    solicitar_ciudad_registro(),
                ],
            }
        return {
            "success": True,
            "messages": [solicitar_ciudad_registro()],
        }

    canonica, estado_validacion = validar_y_normalizar_ubicacion(ciudad)
    if estado_validacion == VALIDATION_ERROR_TOO_SHORT:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_corta()}],
        }
    if estado_validacion == VALIDATION_ERROR_TOO_LONG:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_larga()}],
        }
    if estado_validacion == VALIDATION_ERROR_INVALID_CHARS:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_caracteres_invalidos()}],
        }
    if estado_validacion == VALIDATION_ERROR_MULTIPLE:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_multiple()}],
        }
    if not canonica:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_no_reconocida()}],
        }

    # Persistimos en minúsculas para mantener consistencia histórica.
    ciudad_normalizada = canonica.lower().strip()
    flujo["city"] = ciudad_normalizada
    flujo["city_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    if proveedor_id:
        try:
            await _persistir_ubicacion_proveedor(
                supabase,
                proveedor_id,
                ciudad=ciudad_normalizada,
                latitud=latitud,
                longitud=longitud,
            )
        except Exception:
            pass

    if flujo.get("profile_edit_mode") == "personal_city":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": "✅ Tu ubicación principal fue actualizada correctamente."},
                construir_payload_menu_principal(
                    esta_registrado=True,
                    menu_limitado=bool(flujo.get("menu_limitado")),
                    approved_basic=bool(flujo.get("approved_basic")),
                ),
            ],
        }

    flujo["state"] = "awaiting_name"
    return {
        "success": True,
        "messages": [{"response": preguntar_nombre()}],
    }
