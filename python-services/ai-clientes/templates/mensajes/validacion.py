"""Mensajes de validación y error para entrada de usuario."""

import re
import unicodedata
from typing import Any, Dict, List, Optional

# ==================== MENSAJES ====================

mensaje_inicial_solicitud_servicio = (
    "*¿Qué necesitas resolver?*. Puedes ver un *listado de servicios populares* "
    "o escribir directamente el *problema o necesidad*."
)
mensaje_error_solicitud_servicio_corto = "*¿Qué necesitas resolver?*."

POPULAR_SERVICE_PREFIX = "popular_service::"
DEFAULT_POPULAR_SERVICES = [
    "Plomero",
    "Electricista",
    "Técnico de lavadoras",
    "Cerrajero",
    "Limpieza del hogar",
]

mensaje_error_input_invalido = mensaje_error_solicitud_servicio_corto

mensaje_advertencia_contenido_ilegal = """⚠️ *ADVERTENCIA*

TinkuBot NO conecta servicios de contenido ilegal o inapropiado.

Si vuelves a insistir con este tipo de contenido, tu cuenta será suspendida temporalmente.

Por favor, describe un servicio legítimo que necesites."""

mensaje_ban_usuario = """🚫 *CUENTA SUSPENDIDA TEMPORALMENTE*

Has sido suspendido por 15 minutos por infringir nuestras políticas de contenido.

Podrás reanudar el servicio después de las {hora_reinicio}."""

mensaje_error_input_sin_sentido = mensaje_error_solicitud_servicio_corto


def mensaje_solicitar_detalle_servicio(servicio_hint: Optional[str] = None) -> str:
    """Pide al usuario describir el problema antes de buscar proveedores."""
    hint = (servicio_hint or "").strip()
    if hint:
        return f"Por favor, cuéntame para qué necesitas un *{hint}*."
    return "Por favor, cuéntame brevemente qué necesitas."


def mensaje_solicitar_precision_servicio(servicio: str) -> str:
    """Pide mayor precisión cuando el servicio detectado es demasiado general."""
    servicio_norm = _slug_servicio(servicio).replace("_", " ")
    if servicio_norm in {
        "transporte mercancias",
        "transporte mercaderia",
        "transporte de mercancias",
        "transporte de mercaderia",
        "transporte carga",
        "transporte de carga",
        "transporte terrestre",
        "transporte maritimo",
        "transporte aereo",
    }:
        return (
            "Para ubicar el servicio correcto, dime si el transporte es "
            "*terrestre, marítimo o aéreo*, y si es *local, nacional o internacional*."
        )
    if servicio_norm in {"asesoria legal", "servicio legal", "legal"}:
        return (
            "Para ubicar el servicio correcto, dime el *trámite o área legal exacta* "
            "(ej: laboral, familia, tributario, penal, contratación pública)."
        )
    if servicio_norm in {
        "servicios tecnologicos",
        "servicio tecnologico",
        "consultoria tecnologica",
        "consultoria tecnologia",
        "desarrollo tecnologico",
    }:
        return (
            "Para ubicar el servicio correcto, dime el *tipo exacto de solución* "
            "(ej: desarrollo web, redes, soporte técnico, cableado estructurado)."
        )
    return "Por favor, cuéntame con más precisión qué necesitas."


def solicitar_reformulacion() -> str:
    """Solicita al usuario reformular su mensaje."""
    return "¿Podrías reformular tu mensaje?"


def _slug_servicio(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    base = re.sub(r"[^a-z0-9]+", "_", sin_acentos)
    return base.strip("_")[:64] or "servicio"


def construir_opciones_servicios_populares(
    servicios: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Construye opciones de lista para servicios populares."""
    lista = []
    vistos = set()
    for idx, item in enumerate((servicios or DEFAULT_POPULAR_SERVICES), start=1):
        servicio = (item or "").strip()
        if not servicio:
            continue
        titulo = f"Top {idx}"
        if not titulo:
            continue
        clave = servicio.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        lista.append(
            {
                "id": f"{POPULAR_SERVICE_PREFIX}{_slug_servicio(servicio)}",
                "title": titulo[:24],
                "description": servicio[:72],
            }
        )
        if len(lista) == 5:
            break
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
    def _resolver_servicio_por_slug(slug: str) -> str:
        catalogo = (servicios or []) + DEFAULT_POPULAR_SERVICES
        for item in catalogo:
            nombre = (item or "").strip()
            if not nombre:
                continue
            if _slug_servicio(nombre) == slug:
                return nombre
        return slug.replace("_", " ").strip().title()

    selected = (selected_option or "").strip().lower()
    if not selected:
        return None
    if selected.startswith(POPULAR_SERVICE_PREFIX):
        slug = selected[len(POPULAR_SERVICE_PREFIX) :].strip("_ ")
        if not slug:
            return None
        return _resolver_servicio_por_slug(slug)
    if servicios:
        mapa = {
            opcion["id"].strip().lower(): opcion.get("description") or opcion["title"]
            for opcion in construir_opciones_servicios_populares(servicios)
            if opcion.get("id") and opcion.get("title")
        }
        return mapa.get(selected)
    return None


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
