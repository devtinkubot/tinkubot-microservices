"""Compatibilidad local para legacy de perfil, documentos y onboarding."""

from typing import Any, Dict, Optional

import flows.maintenance.document_update as legacy_document_update
import flows.maintenance.selfie_update as legacy_selfie_update
import flows.maintenance.wait_certificate as legacy_wait_certificate
import flows.maintenance.wait_experience as legacy_wait_experience
import flows.maintenance.wait_name as legacy_wait_name
import services.onboarding.ciudad as legacy_onboarding_city
import services.onboarding.real_phone as legacy_onboarding_real_phone


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
    return await legacy_onboarding_real_phone.manejar_espera_real_phone_onboarding(
        flujo,
        texto_mensaje,
    )


async def manejar_espera_ciudad_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    *,
    carga: Dict[str, Any],
    supabase: Any,
    proveedor_id: Optional[str],
):
    return await legacy_onboarding_city.manejar_espera_ciudad_onboarding(
        flujo,
        texto_mensaje,
        carga=carga,
        supabase=supabase,
        proveedor_id=proveedor_id,
    )
