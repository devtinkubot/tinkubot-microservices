"""Textos base reutilizables para el servicio de clientes."""

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

SEPARATOR_LINE = ".................."


def provider_options_intro(city: str) -> str:
    if city:
        return f"**Encontré estas opciones en {city}:**"
    return "**Encontré estas opciones para ti:**"


def provider_options_block(providers: List[Dict[str, Any]]) -> str:
    def format_price(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, (int, float)) and raw > 0:
            return f"USD {raw:.2f}".rstrip("0").rstrip(".")
        return str(raw).strip()

    lines: List[str] = [SEPARATOR_LINE, ""]
    for idx, provider in enumerate(providers, start=1):
        name = (
            provider.get("name") or provider.get("provider_name") or "Proveedor"
        ).strip()
        service = (
            provider.get("service_title")
            or provider.get("service")
            or provider.get("profession")
            or ""
        ).strip()
        price = format_price(
            provider.get("price_formatted")
            or provider.get("price_display")
            or provider.get("price")
        )
        details: List[str] = []
        if service and service.lower() not in name.lower():
            details.append(service)
        if price:
            details.append(price)
        detail_suffix = f" — {' — '.join(details)}" if details else ""
        lines.append(f"{idx}. {name}{detail_suffix}")
    lines.extend(["", SEPARATOR_LINE])
    return "\n".join(lines)


def provider_options_prompt(_: int) -> str:
    return "**Responde con el número de tu opción (o 0 para cambiar de ciudad):**"


def provider_no_results_block(city: str) -> str:
    lines = [
        provider_options_intro(city),
        "",
        SEPARATOR_LINE,
        "",
        "    -- No tenemos aún proveedores --",
        "",
        SEPARATOR_LINE,
    ]
    return "\n".join(lines)


def provider_no_results_prompt() -> str:
    return ""


def consent_options_block() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    lines = [
        SEPARATOR_LINE,
        "",
        "1 Acepto",
        "2 No acepto",
        "",
        SEPARATOR_LINE,
    ]
    return "\n".join(lines)


def consent_prompt_messages() -> List[str]:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [f"{CONSENT_PROMPT}\n\n{consent_options_block()}", CONFIRM_PROMPT_FOOTER]


def confirm_options_block(
    include_city_option: bool = False, include_provider_option: bool = False
) -> str:
    lines = [
        SEPARATOR_LINE,
        "",
    ]
    if include_provider_option:
        lines.append("0 Elegir otro proveedor")
    elif include_city_option:
        lines.append("0 Buscar en otra ciudad")
    lines.extend(
        [
            f"1 {CONFIRM_NEW_SEARCH_BUTTONS[0]}",
            f"2 {CONFIRM_NEW_SEARCH_BUTTONS[1]}",
            "",
            SEPARATOR_LINE,
        ]
    )
    return "\n".join(lines)
