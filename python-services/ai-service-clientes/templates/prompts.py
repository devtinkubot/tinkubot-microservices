"""Textos base reutilizables para el servicio de clientes."""

from typing import Any, Dict, List

# Mantener este módulo enfocado en textos y plantillas simples para evitar
# mezclar lógica de flujo con contenido.

INITIAL_PROMPT = "*¿En qué te puedo ayudar hoy?*"

CONFIRM_NEW_SEARCH_BUTTONS = [
    "Sí, buscar otro servicio",
    "No, por ahora está bien",
]
CONFIRM_PROMPT_TITLE_DEFAULT = "¿Te ayudo con otro servicio?"
CONFIRM_PROMPT_FOOTER = "**Responde con el número de tu opción (o 0 para cambiar de ciudad):**"

SEPARATOR_LINE = ".................."

def ascii_block(lines: List[str]) -> str:
    if not lines:
        lines = [""]
    width = max(len(line) for line in lines)
    border = " " + "." * (width + 3)
    body = [f" {line.ljust(width)} " for line in lines]
    return "\n".join([border, "", *body, "", border])


# Bloque ASCII para guiar la selección del alcance del servicio.
SCOPE_PROMPT_TITLE = "*¿Deseas que el servicio sea?*"
_SCOPE_PROMPT_LINES = [
    "*1* Inmediato",
    "*2* Puedo esperar",
]
SCOPE_PROMPT_BLOCK = ascii_block(_SCOPE_PROMPT_LINES)
SCOPE_PROMPT_FOOTER = "Responde con el número de tu opción:"


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
            provider.get("name")
            or provider.get("provider_name")
            or "Proveedor"
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


def confirm_options_block() -> str:
    lines = [
        SEPARATOR_LINE,
        "",
        f"1 {CONFIRM_NEW_SEARCH_BUTTONS[0]}",
        f"2 {CONFIRM_NEW_SEARCH_BUTTONS[1]}",
        "",
        SEPARATOR_LINE,
    ]
    return "\n".join(lines)
