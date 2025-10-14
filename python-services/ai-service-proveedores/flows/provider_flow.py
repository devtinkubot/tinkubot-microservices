"""Logica del flujo conversacional para registro de proveedores."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


def normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def parse_experience_years(text: str) -> Optional[int]:
    normalized = (text or "").strip().lower()
    if normalized in {"omitir", "ninguna", "no", "na", "n/a"}:
        return 0

    numbers = ""
    for char in normalized:
        if char.isdigit():
            numbers += char
        elif numbers:
            break

    if not numbers:
        return None

    try:
        return max(0, min(60, int(numbers)))
    except Exception:
        return None


class ProviderFlow:
    """Encapsula manejadores de cada estado del flujo de registro."""

    @staticmethod
    def handle_awaiting_name(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        name = normalize_text(message_text)
        if len(name) < 2:
            return {
                "success": True,
                "response": "Por favor, enviame tu nombre completo.",
            }

        flow["name"] = name
        flow["state"] = "awaiting_profession"
        return {
            "success": True,
            "response": "Gracias. Cual es tu profesion u oficio? (ej: plomero, electricista)",
        }

    @staticmethod
    def handle_awaiting_profession(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        profession = normalize_text(message_text)
        if len(profession) < 2:
            return {
                "success": True,
                "response": "Indica tu profesion u oficio (ej: plomero, electricista).",
            }

        flow["profession"] = profession
        flow["state"] = "awaiting_city"
        return {
            "success": True,
            "response": "En que ciudad trabajas principalmente?",
        }

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        city = normalize_text(message_text)
        if len(city) < 2:
            return {
                "success": True,
                "response": "Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).",
            }

        flow["city"] = city
        flow["state"] = "awaiting_address"
        return {
            "success": True,
            "response": "Opcional: tu direccion o sector (puedes responder 'omitir').",
        }

    @staticmethod
    def handle_awaiting_address(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        address = normalize_text(message_text)
        if address.lower() in {"omitir", "na", "n/a", "ninguna"}:
            flow["address"] = None
        else:
            flow["address"] = address

        flow["state"] = "awaiting_email"
        return {
            "success": True,
            "response": "Opcional: tu correo electronico (o escribe 'omitir').",
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
                "response": "El correo no parece valido. Envialo nuevamente o escribe 'omitir'.",
            }

        flow["email"] = email
        flow["state"] = "awaiting_experience"
        return {
            "success": True,
            "response": "Cuantos anos de experiencia tienes? (puedes escribir un numero o 'omitir')",
        }

    @staticmethod
    def handle_awaiting_experience(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        years = parse_experience_years(message_text or "")
        if years is None:
            return {
                "success": True,
                "response": "Por favor envia un numero de anos (ej: 5) o escribe 'omitir'.",
            }

        flow["experience_years"] = years
        flow["state"] = "awaiting_dni"
        return {
            "success": True,
            "response": "Para completar tu verificacion, cual es tu numero de DNI? (puedes responder 'omitir' si prefieres)",
        }

    @staticmethod
    def handle_awaiting_dni(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        dni = normalize_text(message_text)
        if dni.lower() in {"omitir", "na", "n/a", "ninguno"}:
            flow["dni_number"] = None
        elif len(dni) < 5 or len(dni) > 20:
            return {
                "success": True,
                "response": "El DNI debe tener entre 5 y 20 caracteres. Envialo nuevamente o escribe 'omitir'.",
            }
        else:
            flow["dni_number"] = dni

        flow["state"] = "awaiting_social_media"
        return {
            "success": True,
            "response": "Opcional: Tienes Facebook o Instagram? Envia tu usuario o escribe 'omitir'.",
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

        flow["state"] = "confirm"

        summary = (
            "Por favor confirma tus datos:\n"
            f"- Nombre: {flow.get('name')}\n"
            f"- Profesion: {flow.get('profession')}\n"
            f"- Ciudad: {flow.get('city')}\n"
            f"- Email: {flow.get('email') or 'No especificado'}\n"
            f"- Experiencia: {flow.get('experience_years')} anos\n"
            f"- DNI: {flow.get('dni_number') or 'No especificado'}\n"
            f"- Red Social: {flow.get('social_media_url') or 'No especificada'}\n\n"
            "Responde 'confirmar' para guardar o 'editar' para corregir."
        )

        return {"success": True, "response": summary}

    @staticmethod
    async def handle_confirm(
        flow: Dict[str, Any],
        message_text: Optional[str],
        phone: str,
        register_provider_fn: Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]],
        reset_flow_fn: Callable[[], Awaitable[None]],
        logger: Any,
    ) -> Dict[str, Any]:
        text = normalize_text(message_text).lower()
        if text.startswith("editar"):
            flow["state"] = "awaiting_name"
            return {
                "success": True,
                "response": "De acuerdo, actualicemos los datos. Cual es tu nombre completo?",
            }

        if text.startswith("confirm") or text in {"si", "ok", "listo"}:
            provider_data = {
                "phone": phone,
                "name": flow.get("name"),
                "email": flow.get("email"),
                "city": flow.get("city"),
                "profession": flow.get("profession"),
                "experience_years": flow.get("experience_years"),
                "dni_number": flow.get("dni_number"),
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
                await reset_flow_fn()
                return {
                    "success": True,
                    "response": "Registro completado! Tu perfil ha sido creado con verificacion de identidad. Cuando quieras, puedes agregar mas servicios o actualizar tus datos.",
                    "reset_flow": True,
                }

            logger.error("No se pudo registrar el proveedor")
            return {
                "success": False,
                "response": "Hubo un error al guardar tu informacion. Por favor intenta de nuevo.",
            }

        return {
            "success": True,
            "response": "Por favor escribe 'confirmar' para guardar o 'editar' para corregir.",
        }
