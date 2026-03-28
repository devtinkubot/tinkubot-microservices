"""Handler de onboarding para el paso de ciudad."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.onboarding.event_payloads import payload_ciudad
from services.onboarding.event_publisher import (
    EVENT_TYPE_CITY,
    onboarding_async_persistence_enabled,
    publicar_evento_onboarding,
)
from templates.onboarding.ciudad import (
    solicitar_ciudad_registro,
)
from templates.onboarding.documentos import payload_onboarding_dni_frontal
from utils import limpiar_espacios


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
        ciudad = _normalizar_ciudad_desde_texto(ubicacion.get(campo))
        if ciudad:
            return ciudad
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
    ciudad = limpiar_espacios(texto_mensaje)
    ubicacion = (carga or {}).get("location") or {}
    latitud = _parsear_coordenada((ubicacion or {}).get("latitude"))
    longitud = _parsear_coordenada((ubicacion or {}).get("longitude"))
    ciudad_desde_payload = _extraer_ciudad_desde_payload_ubicacion(ubicacion)
    ciudad_candidata = ciudad_desde_payload or ciudad
    tiene_ubicacion_estructurada = bool(
        ciudad_desde_payload or (latitud is not None and longitud is not None)
    )

    if latitud is not None:
        flujo["location_lat"] = latitud
    if longitud is not None:
        flujo["location_lng"] = longitud
    if latitud is not None or longitud is not None:
        flujo["location_updated_at"] = datetime.now(timezone.utc).isoformat()
    if not ciudad_candidata and not tiene_ubicacion_estructurada:
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
