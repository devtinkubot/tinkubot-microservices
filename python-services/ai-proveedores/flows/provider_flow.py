"""Logica del flujo conversacional para registro de proveedores."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


from models.schemas import ProviderCreate
from templates.prompts import (
    provider_under_review_message,
)

from services.parser_service import (
    normalize_text,
    parse_experience_years,
    parse_services_string,
    parse_social_media,
)
from services.validation_service import (
    validate_city,
    validate_email,
    validate_name,
    validate_profession,
    validate_provider_payload,
    validate_specialty,
)






class ProviderFlow:
    """Encapsula manejadores de cada estado del flujo de registro."""

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        city = normalize_text(message_text)
        is_valid, error_message = validate_city(city)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["city"] = city
        flow["state"] = "awaiting_name"
        return {
            "success": True,
            "response": "*¿Cuál es tu nombre completo?*",
        }

    @staticmethod
    def handle_awaiting_name(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        name = normalize_text(message_text)
        is_valid, error_message = validate_name(name)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["name"] = name
        flow["state"] = "awaiting_profession"
        return {
            "success": True,
            "response": (
                '*¿Cuál es tu profesión u oficio? Escribe el título, por ejemplo: '
                '"Carpintero", "Ingeniero Electrico", "Abogado".*'
            ),
        }

    @staticmethod
    def handle_awaiting_profession(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        profession = normalize_text(message_text)
        is_valid, error_message = validate_profession(profession)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["profession"] = profession
        flow["state"] = "awaiting_specialty"
        return {
            "success": True,
            "response": (
                "*¿Qué servicios ofreces dentro de tu profesión?* "
                "Sepáralos con comas (ej: instalación eléctrica, mantenimiento industrial)."
            ),
        }

    @staticmethod
    def handle_awaiting_specialty(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        specialty = normalize_text(message_text)
        is_valid, error_message = validate_specialty(specialty)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["specialty"] = specialty
        flow["state"] = "awaiting_experience"
        return {
            "success": True,
            "response": ("*Cuantos años de experiencia tienes? (escribe un numero)*"),
        }

    @staticmethod
    def handle_awaiting_experience(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        years = parse_experience_years(message_text)
        if years is None:
            return {
                "success": True,
                "response": "*Necesito un numero de años de experiencia (ej: 5).*",
            }

        flow["experience_years"] = years
        flow["state"] = "awaiting_email"
        return {
            "success": True,
            "response": "*Escribe tu correo electrónico o escribe \"omitir\" si no deseas agregarlo.*",
        }

    @staticmethod
    def handle_awaiting_email(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        email = normalize_text(message_text)
        is_valid, error_message, normalized_email = validate_email(email)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["email"] = normalized_email
        flow["state"] = "awaiting_social_media"
        return {
            "success": True,
            "response": (
                "*Tienes alguna red social (Instagram o Facebook) para mostrar tu trabajo? "
                "Envia el enlace o escribe 'omitir'.*"
            ),
        }

    @staticmethod
    def parse_social_media_input(message_text: Optional[str]) -> Dict[str, Optional[str]]:
        """Parsea la entrada de red social y devuelve url + tipo."""
        return parse_social_media(message_text)

    @staticmethod
    def handle_awaiting_social_media(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        parsed = ProviderFlow.parse_social_media_input(message_text)
        flow["social_media_url"] = parsed["url"]
        flow["social_media_type"] = parsed["type"]

        flow["state"] = "awaiting_dni_front_photo"
        return {
            "success": True,
            "response": (
                "*Perfecto. Ahora necesito la foto de la Cédula (parte frontal). "
                "Envia la imagen como adjunto.*"
            ),
        }

    @staticmethod
    def build_confirmation_summary(flow: Dict[str, Any]) -> str:
        email = flow.get("email") or "No especificado"
        social = flow.get("social_media_url") or "No especificada"
        social_type = flow.get("social_media_type")
        if social_type and social and social != "No especificada":
            social = f"{social} ({social_type})"

        front = "Recibida" if flow.get("dni_front_image") else "Pendiente"
        back = "Recibida" if flow.get("dni_back_image") else "Pendiente"
        face = "Recibida" if flow.get("face_image") else "Pendiente"

        experience = flow.get("experience_years")
        experience_text = (
            f"{experience} años"
            if isinstance(experience, int) and experience > 0
            else "Sin especificar"
        )
        specialty = flow.get("specialty") or "No especificada"
        city = flow.get("city") or "No especificada"
        profession = flow.get("profession") or "No especificada"
        name = flow.get("name") or "No especificado"

        lines = [
            "-----------------------------",
            "*Por favor confirma tus datos:*",
            "-----------------------------",
            f"- Ciudad: {city}",
            f"- Nombre: {name}",
            f"- Profesion: {profession}",
            f"- Especialidad: {specialty}",
            f"- Experiencia: {experience_text}",
            f"- Correo: {email}",
            f"- Red Social: {social}",
            f"- Foto Cédula (frente): {front}",
            f"- Foto Cédula (reverso): {back}",
            f"- Selfie: {face}",
            "",
            "-----------------------------",
            "1. Confirmar datos",
            "2. Editar información",
            "-----------------------------",
            "*Responde con el numero de tu opcion:*",
        ]
        return "\n".join(lines)

    @staticmethod
    async def handle_confirm(
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
        raw_text = normalize_text(message_text)
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
            is_valid, result = validate_provider_payload(flow, phone)
            if not is_valid:
                return result

            provider_payload = result

            registered_provider = await register_provider_fn(provider_payload)
            if registered_provider:
                logger.info(
                    "Proveedor registrado exitosamente: %s",
                    registered_provider.get("id"),
                )
                provider_id = registered_provider.get("id")
                servicios_registrados = parse_services_string(
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

    @staticmethod
    def get_supported_states() -> set:
        """
        Retorna el conjunto de estados soportados por ProviderFlow.

        Returns:
            Set con los nombres de estados que ProviderFlow puede manejar
        """
        return {
            "awaiting_city",
            "awaiting_name",
            "awaiting_profession",
            "awaiting_specialty",
            "awaiting_experience",
            "awaiting_email",
            "awaiting_social_media",
            "awaiting_dni_front_photo",
            "awaiting_dni_back_photo",
            "awaiting_face_photo",
            "confirm",
        }
