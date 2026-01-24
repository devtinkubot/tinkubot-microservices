"""Manejador del estado de confirmación (async)."""

import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import ValidationError

from shared_lib.models import ProviderCreate
from templates.prompts import provider_under_review_message
from flows.validators.normalizar_texto import normalizar_texto
from flows.validators.validaciones_entrada import parsear_cadena_servicios


async def manejar_confirmacion(
    flow: Dict[str, Any],
    message_text: Optional[str],
    phone: str,
    register_provider_fn: Callable[
        [ProviderCreate], Awaitable[Optional[Dict[str, Any]]]
    ],
    upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
    reset_flow_fn: Callable[[], Awaitable[None]],
    logger: Any,
) -> Dict[str, Any]:
    """Procesa la confirmación del registro y crea el proveedor.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con confirmación o edición.
        phone: Número de teléfono del proveedor.
        register_provider_fn: Función asíncrona para registrar el proveedor.
        upload_media_fn: Función asíncrona para subir medios.
        reset_flow_fn: Función asíncrona para resetear el flujo.
        logger: Logger para registro de eventos.

    Returns:
        Respuesta con éxito y nuevo estado del flujo, o error de validación.
    """
    raw_text = normalizar_texto(message_text)
    text = raw_text.lower()

    if text.startswith("2") or "editar" in text:
        has_consent = flow.get("has_consent", False)
        flow.clear()
        flow["state"] = "awaiting_city"
        if has_consent:
            flow["has_consent"] = True
        return {
            "success": True,
            "response": ("Reiniciemos. *En que ciudad trabajas principalmente?*"),
        }

    if (
        text.startswith("1")
        or text.startswith("confirm")
        or text in {"si", "ok", "listo", "confirmar"}
    ):
        specialty = flow.get("specialty")
        services_list = []
        if isinstance(specialty, str):
            services_list = [
                item.strip()
                for item in re.split(r"[;,/\n]+", specialty)
                if item and item.strip()
            ]
            if not services_list and specialty.strip():
                services_list = [specialty.strip()]

        try:
            provider_payload = ProviderCreate(
                phone=phone,
                full_name=flow.get("name") or "",
                email=flow.get("email"),
                city=flow.get("city") or "",
                profession=flow.get("profession") or "",
                services_list=services_list,
                experience_years=flow.get("experience_years"),
                has_consent=flow.get("has_consent", False),
                social_media_url=flow.get("social_media_url"),
                social_media_type=flow.get("social_media_type"),
            )
        except ValidationError as exc:
            logger.error("Datos de registro invalidos para %s: %s", phone, exc)
            first_error = exc.errors()[0] if exc.errors() else {}
            reason = first_error.get("msg") or "Datos inválidos"
            return {
                "success": False,
                "response": (
                    f"*No pude validar tus datos:* {reason}. "
                    "Revisa que nombre, ciudad y profesión cumplan con el formato y longitud."
                ),
            }

        registered_provider = await register_provider_fn(provider_payload)
        if registered_provider:
            logger.info(
                "Proveedor registrado exitosamente: %s",
                registered_provider.get("id"),
            )
            provider_id = registered_provider.get("id")
            servicios_registrados = parsear_cadena_servicios(
                registered_provider.get("services")
            )
            flow["services"] = servicios_registrados
            if provider_id:
                await upload_media_fn(provider_id, flow)
            await reset_flow_fn()
            return {
                "success": True,
                "messages": [{"response": provider_under_review_message()}],
                "reset_flow": True,
                "new_flow": {
                    "state": "pending_verification",
                    "has_consent": True,
                    "registration_allowed": False,
                    "provider_id": provider_id,
                    "services": servicios_registrados,
                    "awaiting_verification": True,
                },
            }

        logger.error("No se pudo registrar el proveedor")
        return {
            "success": False,
            "response": (
                "*Hubo un error al guardar tu informacion. Por favor intenta de nuevo.*"
            ),
        }

    return {
        "success": True,
        "response": (
            "*Por favor selecciona 1 para confirmar o 2 para editar tu informacion.*"
        ),
    }
