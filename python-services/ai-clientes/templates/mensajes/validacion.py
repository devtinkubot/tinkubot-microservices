"""Mensajes de validación y error para entrada de usuario."""

import re
from typing import Any, Dict, List, Optional

# ==================== MENSAJES ====================

mensaje_inicial_solicitud_servicio = "*¿Qué necesitas resolver?*. Describe lo que necesitas."

POPULAR_SERVICE_PREFIX = "popular_service::"
OTHER_SERVICE_OPTION_ID = "other_service"
DEFAULT_POPULAR_SERVICES = [
    "Plomero",
    "Electricista",
    "Técnico de lavadoras",
    "Cerrajero",
    "Limpieza del hogar",
]

mensaje_error_input_invalido = mensaje_inicial_solicitud_servicio

mensaje_advertencia_contenido_ilegal = """⚠️ *ADVERTENCIA*

TinkuBot NO conecta servicios de contenido ilegal o inapropiado.

Si vuelves a insistir con este tipo de contenido, tu cuenta será suspendida temporalmente.

Por favor, describe un servicio legítimo que necesites."""

mensaje_ban_usuario = """🚫 *CUENTA SUSPENDIDA TEMPORALMENTE*

Has sido suspendido por 15 minutos por infringir nuestras políticas de contenido.

Podrás reanudar el servicio después de las {hora_reinicio}."""

mensaje_error_input_sin_sentido = mensaje_inicial_solicitud_servicio


def solicitar_reformulacion() -> str:
    """Solicita al usuario reformular su mensaje."""
    return "¿Podrías reformular tu mensaje?"


def _slug_servicio(texto: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (texto or "").strip().lower())
    return base.strip("_")[:64] or "servicio"


def construir_opciones_servicios_populares(
    servicios: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Construye opciones de lista para servicios populares."""
    lista = []
    vistos = set()
    for item in (servicios or DEFAULT_POPULAR_SERVICES):
        titulo = (item or "").strip()
        if not titulo:
            continue
        clave = titulo.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        lista.append(
            {
                "id": f"{POPULAR_SERVICE_PREFIX}{_slug_servicio(titulo)}",
                "title": titulo[:24],
            }
        )
        if len(lista) == 5:
            break
    lista.append({"id": OTHER_SERVICE_OPTION_ID, "title": "Otro servicio"})
    return lista


def construir_prompt_lista_servicios(
    servicios: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Retorna payload de mensaje inicial con lista interactiva."""
    return {
        "response": mensaje_inicial_solicitud_servicio,
        "ui": {
            "type": "list",
            "id": "popular_services_v1",
            "list_button_text": "Servicios populares",
            "list_section_title": "Más solicitados",
            "options": construir_opciones_servicios_populares(servicios),
        },
    }


def extraer_servicio_desde_opcion_lista(
    selected_option: Optional[str],
    servicios: Optional[List[str]] = None,
) -> Optional[str]:
    """Resuelve el servicio elegido desde el id de opción de lista."""
    selected = (selected_option or "").strip().lower()
    if not selected or selected == OTHER_SERVICE_OPTION_ID:
        return None
    if selected.startswith(POPULAR_SERVICE_PREFIX):
        slug = selected[len(POPULAR_SERVICE_PREFIX) :].strip("_ ")
        if not slug:
            return None
        return slug.replace("_", " ").strip().title()
    if servicios:
        mapa = {
            opcion["id"].strip().lower(): opcion["title"]
            for opcion in construir_opciones_servicios_populares(servicios)
            if opcion.get("id") and opcion.get("title")
        }
        return mapa.get(selected)
    return None


def mensaje_otro_servicio_texto_libre() -> str:
    """Prompt para que el usuario escriba un servicio fuera de la lista."""
    return "Perfecto. Escribe el servicio que necesitas."

def mensaje_confirmar_servicio(servicio: str) -> str:
    """Confirma el servicio detectado antes de continuar la búsqueda."""
    servicio_texto = (servicio or "").strip() or "tu solicitud"
    return f"¿Es este el servicio que buscas: *{servicio_texto}*?"


def ui_confirmar_servicio() -> Dict[str, Any]:
    """Config de UI para confirmar el servicio detectado."""
    return {
        "type": "buttons",
        "id": "problem_confirm",
        "options": [
            {"id": "problem_confirm_yes", "title": "Sí, correcto"},
            {"id": "problem_confirm_no", "title": "No, corregir"},
        ],
    }
