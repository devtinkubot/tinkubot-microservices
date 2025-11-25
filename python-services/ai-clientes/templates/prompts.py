"""Textos base reutilizables para el servicio de clientes."""

import re
from typing import Any, Dict, List

# Mantener este módulo enfocado en textos y plantillas simples para evitar
# mezclar lógica de flujo con contenido.

INITIAL_PROMPT = "*Cuéntame, ¿qué servicio necesitas hoy?*"

# Consentimiento de protección de datos
CONSENT_PROMPT = """¡Hola! Soy TinkuBot, tu asistente virtual para encontrar servicios confiables de forma rápida y segura.

Para poder conectararte con proveedores de servicios, necesito tu consentimiento para compartir tus datos de contacto únicamente con los profesionales seleccionados.

📋 *Información que compartiremos:*
• Tu número de teléfono
• Ciudad donde necesitas el servicio
• Tipo de servicio que solicitas

🔒 *Tus datos están seguros y solo se usan para esta consulta.*

*¿Aceptas compartir tus datos con proveedores?*"""

CONSENT_BUTTONS = ["Acepto", "No acepto"]
CONFIRM_NEW_SEARCH_BUTTONS = ["Sí, buscar otro servicio", "No, por ahora está bien"]
CONFIRM_PROMPT_TITLE_DEFAULT = "¿Te ayudo con otro servicio?"
CONFIRM_PROMPT_FOOTER = "*Responde con el número de tu opción:*"


def _bold(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("**") and stripped.endswith("**"):
        return stripped
    stripped = stripped.strip("*")
    return f"**{stripped}**"


def provider_options_intro(city: str) -> str:
    if city:
        return f"**Encontré estas opciones en {city}:**"
    return "**Encontré estas opciones para ti:**"


def provider_options_block(providers: List[Dict[str, Any]]) -> str:
    """Genera listado de proveedores con letras (a-e) y solo nombre."""
    lines: List[str] = [""]
    for idx, provider in enumerate(providers[:5], start=1):
        letter = chr(ord("a") + idx - 1)
        name = (
            provider.get("name") or provider.get("provider_name") or "Proveedor"
        ).strip()
        lines.append(f"{letter}) {name}")
    lines.append("")
    return "\n".join(lines)


def provider_options_prompt(_: int) -> str:
    lines = [
        "**Responde con la letra (a-e) del proveedor para ver detalles.**",
        "",
        "1) Buscar un nuevo servicio",
        "2) Cambiar de Ciudad",
        "3) Salir",
    ]
    return "\n".join(lines)


def provider_detail_block(provider: Dict[str, Any]) -> str:
    """Ficha detallada del proveedor con submenú numérico."""

    def parse_services(raw: Any) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        text = str(raw).strip()
        if not text:
            return []
        parts = [
            part.strip() for part in re.split(r"[;,/|\n]+", text) if part.strip()
        ]
        return parts

    def prettify(text: Any) -> str:
        if text is None:
            return ""
        val = str(text).strip()
        if not val:
            return ""
        return val[0].upper() + val[1:]

    def format_price(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, (int, float)) and raw > 0:
            return f"USD {raw:.2f}".rstrip("0").rstrip(".")
        return str(raw).strip()

    def format_line(label: str, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return f"{label}: {text}" if text else ""

    name = (
        provider.get("name")
        or provider.get("provider_name")
        or provider.get("full_name")
        or "Proveedor"
    )
    profession = provider.get("profession") or provider.get("service_title") or ""
    if not profession and isinstance(provider.get("professions"), list):
        profession = ", ".join(
            [
                str(item).strip()
                for item in provider.get("professions")
                if str(item).strip()
            ]
        )
    profession = prettify(profession)
    city = prettify(provider.get("city") or provider.get("location_city") or "")
    province = prettify(provider.get("province") or provider.get("state") or "")
    price = format_price(
        provider.get("price_formatted")
        or provider.get("price_display")
        or provider.get("price")
    )
    experience = (
        provider.get("experience_years")
        or provider.get("experienceYears")
        or provider.get("years_of_experience")
    )
    rating = provider.get("rating")
    social_url = provider.get("social_media_url") or provider.get("socialMediaUrl")
    social_type = provider.get("social_media_type") or provider.get("socialMediaType")
    services = parse_services(
        provider.get("services_list")
        or provider.get("servicesList")
        or provider.get("services")
        or provider.get("servicesRaw")
    )
    services = [prettify(svc) for svc in services if prettify(svc)]

    location = ", ".join([val for val in [city, province] if val])
    lines: List[str] = ["", _bold(name)]
    for entry in [
        format_line("Profesión", profession),
        format_line("Ubicación", location),
        format_line(
            "Experiencia",
            f"{int(experience)} año(s)" if isinstance(experience, (int, float)) else experience,
        ),
    ]:
        if entry:
            lines.append(entry)

    if services:
        lines.append("Servicios:")
        lines.extend([f"• {svc}" for svc in services])

    if price:
        lines.append(format_line("Precio", price))

    social_line = format_line(
        "Redes",
        f"{social_type}: {social_url}" if social_url and social_type else social_url,
    )
    if social_line:
        lines.append(social_line)

    rating_line = format_line(
        "Calificación", f"{rating:.1f}" if isinstance(rating, (int, float)) else rating
    )
    if rating_line:
        lines.append(rating_line)

    lines.append("")
    return "\n".join(lines)


def provider_detail_options_prompt() -> str:
    """Bloque de acciones para detalle de proveedor."""
    return "\n".join(
        [
            CONFIRM_PROMPT_FOOTER,
            "",
            "1) Elegir",
            "2) Regresar al listado de proveedores",
            "3) Buscar un nuevo servicio",
        ]
    )


def provider_no_results_block(city: str) -> str:
    lines = [
        provider_options_intro(city),
        "",
        "    -- No tenemos aún proveedores --",
        "",
    ]
    return "\n".join(lines)


def provider_no_results_prompt() -> str:
    return ""


def consent_options_block() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Acepto",
            "2) No acepto",
        ]
    )


def consent_prompt_messages() -> List[str]:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{CONSENT_PROMPT}",
        f"{CONFIRM_PROMPT_FOOTER}\n\n{consent_options_block()}",
    ]


def confirm_options_block(
    include_city_option: bool = False, include_provider_option: bool = False
) -> str:
    lines = [CONFIRM_PROMPT_FOOTER, ""]
    if include_provider_option:
        lines.append("0) Elegir otro proveedor")
    elif include_city_option:
        lines.append("0) Buscar en otra ciudad")
    lines.extend(
        [
            f"1) {CONFIRM_NEW_SEARCH_BUTTONS[0]}",
            f"2) {CONFIRM_NEW_SEARCH_BUTTONS[1]}",
            "",
        ]
    )
    return "\n".join(lines)
