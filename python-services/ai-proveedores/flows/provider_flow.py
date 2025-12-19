"""Logica del flujo conversacional para registro de proveedores."""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import ValidationError

from shared_lib.models import ProviderCreate
from templates.prompts import (
    provider_post_registration_menu_message,
    provider_under_review_message,
)


def normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def parse_experience_years(text: Optional[str]) -> Optional[int]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None

    digits = ""
    for ch in normalized:
        if ch.isdigit():
            digits += ch
        elif digits:
            break

    if not digits:
        return None

    try:
        value = int(digits)
    except ValueError:
        return None

    return max(0, min(60, value))


class ProviderFlow:
    """Encapsula manejadores de cada estado del flujo de registro."""

    @staticmethod
    def parse_services_string(value: Optional[str]) -> List[str]:
        if not value:
            return []

        cleaned = value.strip()
        if not cleaned:
            return []

        if re.search(r"[|;,\n]", cleaned):
            candidates = re.split(r"[|;,\n]+", cleaned)
        else:
            candidates = [cleaned]

        servicios: List[str] = []
        for item in candidates:
            servicio = item.strip()
            if servicio and servicio not in servicios:
                servicios.append(servicio)
        return servicios[:5]

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        city = normalize_text(message_text)
        if len(city) < 2:
            return {
                "success": True,
                "response": "*Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).*",
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
        if len(name) < 2:
            return {
                "success": True,
                "response": "*Por favor, enviame tu nombre completo.*",
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
        if len(profession) < 2:
            return {
                "success": True,
                "response": (
                    '*Indica tu profesión u oficio. Ejemplos: "Carpintero", '
                    '"Ingeniero Electrico", "Abogado".*'
                ),
            }
        if len(profession) > 150:
            return {
                "success": True,
                "response": (
                    "*Tu profesión debe ser breve (máximo 150 caracteres).* "
                    "Envía una versión resumida (ej: 'Ingeniera en marketing' o 'Contratación pública')."
                ),
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
        lowered = specialty.lower()
        if lowered in {"omitir", "ninguna", "na", "n/a"}:
            return {
                "success": True,
                "response": (
                    "*La especialidad es obligatoria. Por favor escríbela tal como la trabajas, separando con comas si hay varias.*"
                ),
            }

        if len(specialty) < 2:
            return {
                "success": True,
                "response": (
                    "*La especialidad debe tener al menos 2 caracteres. "
                    "Incluye tus servicios separados por comas (ej: gasfitería, mantenimiento).*"
                ),
            }

        if len(specialty) > 300:
            return {
                "success": True,
                "response": (
                    "*El listado de servicios es muy largo (máx. 300 caracteres).* "
                    "Envía una versión resumida con tus principales servicios separados por comas."
                ),
            }

        services_list = [
            item.strip()
            for item in re.split(r"[;,/\n]+", specialty)
            if item and item.strip()
        ]

        if len(services_list) > 10:
            return {
                "success": True,
                "response": (
                    "*Incluye máximo 10 servicios.* Envía nuevamente tus principales servicios separados por comas."
                ),
            }

        if any(len(srv) > 120 for srv in services_list):
            return {
                "success": True,
                "response": (
                    "*Cada servicio debe ser breve (máx. 120 caracteres).* "
                    "Recorta descripciones muy largas y envía de nuevo la lista."
                ),
            }

        flow["specialty"] = ", ".join(services_list) if services_list else specialty
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
        if email.lower() in {"omitir", "na", "n/a", "ninguno", "ninguna"}:
            email = None
        elif "@" not in email or "." not in email:
            return {
                "success": True,
                "response": (
                    "*El correo no parece valido. Envialo nuevamente o escribe 'omitir'.*"
                ),
            }

        flow["email"] = email
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
        social = normalize_text(message_text)
        if social.lower() in {"omitir", "na", "n/a", "ninguno"}:
            return {"url": None, "type": None}
        if "facebook.com" in social or "fb.com" in social:
            return {"url": social, "type": "facebook"}
        if "instagram.com" in social or "instagr.am" in social:
            return {"url": social, "type": "instagram"}
        return {"url": f"https://instagram.com/{social}", "type": "instagram"}

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
                servicios_registrados = ProviderFlow.parse_services_string(
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
