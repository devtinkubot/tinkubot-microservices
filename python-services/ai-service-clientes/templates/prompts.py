"""Textos base reutilizables para el servicio de clientes."""

# Mantener este módulo enfocado en textos y plantillas simples para evitar
# mezclar lógica de flujo con contenido.

INITIAL_PROMPT = "¿En qué te puedo ayudar hoy?"

# Bloque ASCII para guiar la selección del alcance del servicio; se retorna en un
# bloque monoespaciado para asegurar la alineación en WhatsApp.
SCOPE_PROMPT_TITLE = "Deseas que el servicio sea?"
SCOPE_PROMPT_BLOCK = (
    "```\n"
    "..................................\n"
    "         Opciones:\n"
    " *1*  Cerca y Urgente\n"
    " *2*  Cerca pero puedo esperar\n"
    " *3*  Toda la ciudad\n"
    "..................................\n"
    "```\n"
)
SCOPE_PROMPT_FOOTER = "Escriba una opción (*1*-*3*)"

