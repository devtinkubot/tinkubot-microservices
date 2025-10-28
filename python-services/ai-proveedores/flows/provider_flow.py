"""Logica del flujo conversacional para registro de proveedores."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from templates.prompts import provider_post_registration_menu_message


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
            "response": "*¿Qué profesion u oficio ofreces?*",
        }

    @staticmethod
    def handle_awaiting_profession(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        profession = normalize_text(message_text)
        if len(profession) < 2:
            return {
                "success": True,
                "response": "*Indica tu profesion u oficio (ej: plomero, electricista).*",
            }

        flow["profession"] = profession
        flow["state"] = "awaiting_specialty"
        return {
            "success": True,
            "response": "*Que servicios ofreces dentro de tu profesion?*",
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
                    "*La especialidad es obligatoria. Por favor escribela tal como la trabajas.*"
                ),
            }

        if len(specialty) < 2:
            return {
                "success": True,
                "response": ("*La especialidad debe tener al menos 2 caracteres.*"),
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
            "response": "*Tienes un correo electronico donde pueda escribirte? (responde el correo o 'omitir')*",
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
    def handle_awaiting_social_media(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        social = normalize_text(message_text)
        if social.lower() in {"omitir", "na", "n/a", "ninguno"}:
            flow["social_media_url"] = None
            flow["social_media_type"] = None
        elif "facebook.com" in social or "fb.com" in social:
            flow["social_media_url"] = social
            flow["social_media_type"] = "facebook"
        elif "instagram.com" in social or "instagr.am" in social:
            flow["social_media_url"] = social
            flow["social_media_type"] = "instagram"
        else:
            flow["social_media_url"] = f"https://instagram.com/{social}"
            flow["social_media_type"] = "instagram"

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
            [Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]
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
            provider_data = {
                "phone": phone,
                "name": flow.get("name"),
                "email": flow.get("email"),
                "city": flow.get("city"),
                "profession": flow.get("profession"),
                "specialty": flow.get("specialty"),
                "experience_years": flow.get("experience_years"),
                "dni_number": None,
                "social_media_url": flow.get("social_media_url"),
                "social_media_type": flow.get("social_media_type"),
                "has_consent": flow.get("has_consent", False),
            }

            registered_provider = await register_provider_fn(provider_data)
            if registered_provider:
                logger.info(
                    "Proveedor registrado exitosamente: %s",
                    registered_provider.get("id"),
                )
                provider_id = registered_provider.get("id")
                if provider_id:
                    await upload_media_fn(provider_id, flow)
                await reset_flow_fn()
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "Registro completado! Tu perfil ha sido creado con verificacion de identidad."
                            ),
                        },
                        {"response": provider_post_registration_menu_message()},
                    ],
                    "reset_flow": True,
                    "new_flow": {
                        "state": "awaiting_menu_option",
                        "has_consent": True,
                        "registration_allowed": False,
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
