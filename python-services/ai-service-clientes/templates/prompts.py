"""Textos base reutilizables para el servicio de clientes."""

from typing import Any, Dict, List

# Mantener este módulo enfocado en textos y plantillas simples para evitar
# mezclar lógica de flujo con contenido.

INITIAL_PROMPT = "¿En qué te puedo ayudar hoy?"

CONFIRM_NEW_SEARCH_BUTTONS = [
    "Sí, buscar otro servicio",
    "No, por ahora está bien",
]
CONFIRM_PROMPT_TITLE_DEFAULT = "¿Quieres buscar otro servicio?"
CONFIRM_PROMPT_FOOTER = "Responde con el número de tu opción:"

BLOCK_MIN_WIDTH = 32

def ascii_block(lines: List[str]) -> str:
    if not lines:
        lines = [""]
    width = max(len(line) for line in lines)
    width = max(width, BLOCK_MIN_WIDTH)
    border = " " + "." * (width + 2)
    body = [f" {line.ljust(width)} " for line in lines]
    return "```\n" + "\n".join([border, *body, border]) + "\n```"


# Bloque ASCII para guiar la selección del alcance del servicio.
SCOPE_PROMPT_TITLE = "Deseas que el servicio sea?"
_SCOPE_PROMPT_LINES = [
    "*1* Cerca y Urgente",
    "*2* Cerca pero puedo esperar",
    "*3* Toda la ciudad",
]
SCOPE_PROMPT_BLOCK = ascii_block(_SCOPE_PROMPT_LINES)
SCOPE_PROMPT_FOOTER = "Responde con el número de tu opción:"


def provider_options_intro(city: str) -> str:
    if city:
        return f"Encontré estas opciones en {city}:"
    return "Encontré estas opciones para ti:"


def provider_options_block(providers: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, provider in enumerate(providers, start=1):
        name = (provider.get("name") or "Proveedor").strip()
        lines.append(f"*{idx}* {name}")
    return ascii_block(lines)


def provider_options_prompt(_: int) -> str:
    return "Responde con el número de tu opción:"


def confirm_options_block() -> str:
    lines = [
        f"*1* {CONFIRM_NEW_SEARCH_BUTTONS[0]}",
        f"*2* {CONFIRM_NEW_SEARCH_BUTTONS[1]}",
    ]
    return ascii_block(lines)


# Bloques para solicitud de feedback
FEEDBACK_PROMPT_TITLE = "Califica tu experiencia"
FEEDBACK_PROMPT_FOOTER = "Responde con el número de tu opción:"
FEEDBACK_OPTIONS = {
    1: "Muy mala",
    2: "Mala",
    3: "Regular",
    4: "Buena",
    5: "Excelente",
}


def feedback_options_block() -> str:
    lines = [f"*{idx}* {label}" for idx, label in FEEDBACK_OPTIONS.items()]
    return ascii_block(lines)
