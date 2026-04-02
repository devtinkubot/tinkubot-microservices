"""Compatibilidad local para legacy de perfil, documentos y onboarding."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
import flows.maintenance.document_update as legacy_document_update
import flows.maintenance.selfie_update as legacy_selfie_update
import flows.maintenance.wait_certificate as legacy_wait_certificate
import flows.maintenance.wait_experience as legacy_wait_experience
import flows.maintenance.wait_name as legacy_wait_name
from templates.maintenance.ciudad import (
    preguntar_ciudad,
    solicitar_ciudad_registro,
)
from templates.maintenance.documentos import payload_onboarding_dni_frontal
from templates.maintenance.telefono import error_real_phone_invalido
from utils import limpiar_espacios


def manejar_dni_frontal_actualizacion(flujo: Dict[str, Any], carga: Dict[str, Any]):
    return legacy_document_update.manejar_dni_frontal_actualizacion(flujo, carga)


async def manejar_dni_trasera_actualizacion(
    *,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    proveedor_id: Optional[str],
    subir_medios_identidad: Any,
):
    return await legacy_document_update.manejar_dni_trasera_actualizacion(
        flujo=flujo,
        carga=carga,
        proveedor_id=proveedor_id,
        subir_medios_identidad=subir_medios_identidad,
    )


def manejar_inicio_documentos(flujo: Dict[str, Any]):
    return legacy_document_update.manejar_inicio_documentos(flujo)


async def manejar_actualizacion_selfie(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    carga: Dict[str, Any],
    subir_medios_identidad: Any,
):
    return await legacy_selfie_update.manejar_actualizacion_selfie(
        flujo=flujo,
        proveedor_id=proveedor_id,
        carga=carga,
        subir_medios_identidad=subir_medios_identidad,
    )


async def manejar_espera_certificado(
    *,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
):
    return await legacy_wait_certificate.manejar_espera_certificado(
        flujo=flujo,
        carga=carga,
    )


async def manejar_espera_experiencia(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    *,
    selected_option: Optional[str] = None,
):
    return await legacy_wait_experience.manejar_espera_experiencia(
        flujo,
        texto_mensaje,
        selected_option=selected_option,
    )


async def manejar_espera_nombre(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    *,
    supabase: Any,
    proveedor_id: Optional[str],
):
    return await legacy_wait_name.manejar_espera_nombre(
        flujo,
        texto_mensaje,
        supabase=supabase,
        proveedor_id=proveedor_id,
    )


async def manejar_espera_real_phone_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: str,
):
    real_phone = _normalizar_real_phone(texto_mensaje or "")
    if not real_phone:
        return {
            "success": True,
            "messages": [{"response": error_real_phone_invalido()}],
        }

    flujo["real_phone"] = real_phone
    flujo["requires_real_phone"] = False
    flujo["state"] = "maintenance_city"
    return {
        "success": True,
        "messages": [{"response": preguntar_ciudad()}],
    }


async def manejar_espera_ciudad_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    *,
    carga: Dict[str, Any],
    supabase: Any,
    proveedor_id: Optional[str],
):
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
            return None

    flujo["state"] = "maintenance_dni_front_photo_update"
    return {
        "success": True,
        "messages": [payload_onboarding_dni_frontal()],
    }


def _parsear_coordenada(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _normalizar_real_phone(valor: str) -> Optional[str]:
    limpio = limpiar_espacios(valor)
    if not limpio:
        return None

    compactado = "".join(ch for ch in limpio if ch not in " \t\n\r-().")
    if not compactado:
        return None

    if compactado.startswith("+"):
        digitos = compactado[1:]
    else:
        digitos = compactado

    if not digitos.isdigit():
        return None

    if len(digitos) < 10 or len(digitos) > 20:
        return None

    return _normalizar_telefono_ecuador(compactado)


def _normalizar_telefono_ecuador(telefono: str) -> str:
    if not telefono:
        return telefono

    if telefono.startswith("+"):
        telefono = telefono[1:]

    if len(telefono) == 10 and telefono.startswith("09"):
        telefono = "5939" + telefono[2:]

    return telefono


def _extraer_ciudad_desde_payload_ubicacion(
    ubicacion: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not isinstance(ubicacion, dict):
        return None
    for campo in ("city", "address", "name"):
        ciudad = limpiar_espacios(ubicacion.get(campo)).lower()
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
