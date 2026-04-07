"""Mensajes de validación y error para entrada de usuario."""

import re
import unicodedata
from typing import Any, Dict, List, Optional

# ==================== MENSAJES ====================

mensaje_inicial_solicitud_servicio = (
    "*¿Qué necesitas resolver?*. Puedes escribir directamente el *problema o necesidad*."
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


def mensaje_aclarar_detalle_servicio(servicio_hint: Optional[str] = None) -> str:
    """Aclara qué tipo de detalle esperamos cuando el usuario no entiende."""
    hint = (servicio_hint or "").strip()
    if hint:
        return (
            "Cuéntame brevemente qué necesitas que haga ese profesional. "
            f"Ejemplo: *necesito un {hint} para desarrollar una app móvil*."
        )
    return (
        "Cuéntame brevemente qué necesitas que haga ese profesional. "
        "Ejemplo: *necesito un desarrollador para crear una app móvil*."
    )


def mensaje_solicitar_precision_servicio(servicio: str) -> str:
    """Pide mayor precisión cuando el servicio detectado es demasiado general."""
    servicio_texto = (servicio or "").strip()
    if servicio_texto:
        return (
            f"Para ubicar bien el servicio, cuéntame con más precisión qué necesitas de *{servicio_texto}*."
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
    """Retorna payload de mensaje inicial sin exponer servicios populares."""
    return {
        "response": mensaje_inicial_solicitud_servicio,
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


SPECIALIZATION_PREFIX = "specialization::"


def construir_lista_especializaciones(
    ocupacion: str,
    especializaciones: List[str],
) -> Dict[str, Any]:
    """Construye UI de lista interactiva con especializaciones IA."""
    opciones: List[Dict[str, Any]] = []
    for idx, spec in enumerate(especializaciones[:6], start=1):
        spec_limpio = (spec or "").strip()
        if not spec_limpio:
            continue
        opciones.append(
            {
                "id": f"{SPECIALIZATION_PREFIX}{_slug_servicio(spec_limpio)}",
                "title": f"Opción {idx}",
                "description": spec_limpio[:72],
            }
        )
    if not opciones:
        return {}
    return {
        "type": "list",
        "id": "specialization_list_v1",
        "list_button_text": "Ver opciones",
        "list_section_title": f"Opciones de {(ocupacion or '').strip()[:12]}",
        "options": opciones,
    }


def extraer_especializacion_desde_lista(
    selected_option: Optional[str],
    especializaciones: Optional[List[str]] = None,
) -> Optional[str]:
    """Resuelve la especialización seleccionada por slug."""
    selected = (selected_option or "").strip().lower()
    if not selected.startswith(SPECIALIZATION_PREFIX):
        return None
    slug = selected[len(SPECIALIZATION_PREFIX) :].strip("_ ")
    if not slug:
        return None
    for spec in especializaciones or []:
        if _slug_servicio(spec) == slug:
            return spec
    return slug.replace("_", " ").strip().title()


def mensaje_confirmar_servicio(servicio: str, resumen: str = "") -> str:
    """Confirma el servicio detectado antes de continuar la búsqueda."""
    servicio_texto = (servicio or "").strip() or "tu solicitud"
    resumen_texto = (resumen or "").strip()
    if resumen_texto and resumen_texto.lower() != servicio_texto.lower():
        return f"¿Buscas: *{servicio_texto}*?\n_{resumen_texto}_"
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
