"""Payloads normalizados para side-effects del onboarding."""

from __future__ import annotations

from typing import Any, Dict, List


def payload_consentimiento(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    carga: Dict[str, Any],
    next_state: str,
    real_phone: str | None,
    requires_real_phone: bool,
) -> Dict[str, Any]:
    return {
        "checkpoint": next_state,
        "phone": telefono,
        "raw_phone": flujo.get("phone"),
        "from_number": flujo.get("from_number"),
        "user_id": flujo.get("user_id"),
        "account_id": flujo.get("account_id"),
        "display_name": flujo.get("display_name"),
        "formatted_name": flujo.get("formatted_name"),
        "first_name": flujo.get("first_name"),
        "last_name": flujo.get("last_name"),
        "real_phone": real_phone,
        "requires_real_phone": requires_real_phone,
        "consent_timestamp": carga.get("timestamp"),
        "message_id": carga.get("id") or carga.get("message_id"),
        "exact_response": carga.get("message") or carga.get("content"),
        "platform": carga.get("platform") or "whatsapp",
    }


def payload_real_phone(*, real_phone: str, checkpoint: str) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "real_phone": real_phone,
    }


def payload_ciudad(
    *,
    city: str,
    raw_city_text: str | None,
    location_name: str | None,
    location_address: str | None,
    checkpoint: str,
    location_lat: Any,
    location_lng: Any,
    city_confirmed_at: Any,
    location_updated_at: Any,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "city": city,
        "raw_city_text": raw_city_text,
        "location_name": location_name,
        "location_address": location_address,
        "location_lat": location_lat,
        "location_lng": location_lng,
        "city_confirmed_at": city_confirmed_at,
        "location_updated_at": location_updated_at,
    }


def payload_documento(
    *,
    image_base64: str,
    document_type: str,
    checkpoint: str,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "document_type": document_type,
        "image_base64": image_base64,
    }


def payload_experiencia(
    *,
    experience_range: str,
    checkpoint: str,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "experience_range": experience_range,
    }


def payload_servicios(
    *,
    services: List[str],
    raw_service_text: str,
    service_position: int,
    checkpoint: str,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "services": list(services),
        "raw_service_text": raw_service_text,
        "service_position": service_position,
    }


def payload_redes(
    *,
    facebook_username: str | None,
    instagram_username: str | None,
    social_media_url: str | None,
    social_media_type: str | None,
    checkpoint: str,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "facebook_username": facebook_username,
        "instagram_username": instagram_username,
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
    }


def payload_registro_proveedor(
    *,
    provider_data: Dict[str, Any],
    flujo: Dict[str, Any],
    checkpoint: str,
) -> Dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "provider_data": provider_data,
        "flow": flujo,
    }
