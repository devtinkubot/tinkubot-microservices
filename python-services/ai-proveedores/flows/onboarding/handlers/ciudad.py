"""Handler de onboarding para el paso de ciudad."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from infrastructure.database import run_supabase
from services.onboarding.event_payloads import payload_ciudad
from services.onboarding.event_publisher import (
    EVENT_TYPE_CITY,
    onboarding_async_persistence_enabled,
    publicar_evento_onboarding,
)
from templates.onboarding.ciudad import (
    error_ciudad_no_reconocida,
    solicitar_ciudad_registro,
)
from templates.onboarding.documentos import payload_onboarding_dni_frontal
from services.shared.ubicacion_ecuador import validar_y_normalizar_ubicacion
from utils import limpiar_espacios

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "tinkubot-ai-proveedores/1.0 (support@tinkubot.com)"
GEOCODING_TIMEOUT_SECONDS = 2.5


def _parsear_coordenada(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _normalizar_ciudad_desde_texto(texto: Optional[str]) -> Optional[str]:
    return limpiar_espacios(texto).lower() or None


def _extraer_ciudad_desde_payload_ubicacion(
    ubicacion: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not isinstance(ubicacion, dict):
        return None
    for campo in ("city", "address", "name"):
        ciudad, _estado = validar_y_normalizar_ubicacion(ubicacion.get(campo))
        if ciudad:
            return ciudad
    return None


async def _resolver_ciudad_desde_coordenadas(
    latitud: float, longitud: float
) -> Optional[str]:
    """Resuelve la ciudad/cantón principal usando reverse geocoding."""
    params = {
        "format": "jsonv2",
        "lat": latitud,
        "lon": longitud,
        "zoom": 10,
        "addressdetails": 1,
        "accept-language": "es",
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    timeout = httpx.Timeout(GEOCODING_TIMEOUT_SECONDS)

    async with httpx.AsyncClient(timeout=timeout) as client:
        respuesta = await client.get(
            NOMINATIM_REVERSE_URL, params=params, headers=headers
        )
    if respuesta.status_code != 200:
        return None

    payload = respuesta.json()
    direccion = payload.get("address") or {}
    for campo in ("city", "town", "village", "county", "municipality"):
        ciudad, _estado = validar_y_normalizar_ubicacion(direccion.get(campo))
        if ciudad:
            return ciudad

    display_name, _estado = validar_y_normalizar_ubicacion(payload.get("display_name"))
    return display_name


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
        datos_actualizacion["city_confirmed_at"] = datetime.now(
            timezone.utc
        ).isoformat()
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


async def manejar_espera_ciudad_onboarding(  # noqa: C901
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    carga: Optional[Dict[str, Any]] = None,
    supabase: Any = None,
    proveedor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la entrada de ciudad durante el onboarding."""
    texto_ciudad = limpiar_espacios(texto_mensaje)
    ciudad, _estado_ciudad = validar_y_normalizar_ubicacion(texto_mensaje)
    ubicacion = (carga or {}).get("location") or {}
    latitud = _parsear_coordenada((ubicacion or {}).get("latitude"))
    longitud = _parsear_coordenada((ubicacion or {}).get("longitude"))
    ciudad_desde_payload = _extraer_ciudad_desde_payload_ubicacion(ubicacion)
    ciudad_desde_geocoding = None
    if latitud is not None and longitud is not None:
        try:
            ciudad_desde_geocoding = await _resolver_ciudad_desde_coordenadas(
                latitud, longitud
            )
        except Exception:
            ciudad_desde_geocoding = None
    ciudad_candidata = ciudad_desde_geocoding or ciudad_desde_payload or ciudad
    tiene_ubicacion_estructurada = bool(
        ciudad_desde_payload
        or ciudad_desde_geocoding
        or (latitud is not None and longitud is not None)
    )

    if latitud is not None:
        flujo["location_lat"] = latitud
    if longitud is not None:
        flujo["location_lng"] = longitud
    if latitud is not None or longitud is not None:
        flujo["location_updated_at"] = datetime.now(timezone.utc).isoformat()
    if not ciudad_candidata and not tiene_ubicacion_estructurada:
        if texto_ciudad:
            return {
                "success": True,
                "messages": [{"response": error_ciudad_no_reconocida()}],
            }
        return {
            "success": True,
            "messages": [solicitar_ciudad_registro()],
        }

    ciudad_normalizada = ciudad_candidata.lower().strip() if ciudad_candidata else None
    if ciudad_normalizada:
        flujo["city"] = ciudad_normalizada
    flujo["city_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    if proveedor_id and not onboarding_async_persistence_enabled():
        try:
            await _persistir_ubicacion_proveedor(
                supabase,
                proveedor_id,
                ciudad=ciudad_normalizada,
                latitud=latitud,
                longitud=longitud,
            )
        except Exception:
            return None

    flujo["state"] = "onboarding_dni_front_photo"
    if onboarding_async_persistence_enabled():
        await publicar_evento_onboarding(
            event_type=EVENT_TYPE_CITY,
            flujo=flujo,
            payload=payload_ciudad(
                city=ciudad_normalizada or "",
                raw_city_text=ciudad or None,
                location_name=(ubicacion or {}).get("name"),
                location_address=(ubicacion or {}).get("address"),
                checkpoint="onboarding_dni_front_photo",
                location_lat=flujo.get("location_lat"),
                location_lng=flujo.get("location_lng"),
                city_confirmed_at=flujo.get("city_confirmed_at"),
                location_updated_at=flujo.get("location_updated_at"),
            ),
        )
    return {
        "success": True,
        "messages": [payload_onboarding_dni_frontal()],
    }
