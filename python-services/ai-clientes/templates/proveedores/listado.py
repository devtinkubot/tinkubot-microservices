"""Mensajes relacionados con el listado de proveedores."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from services.proveedores.identidad import resolver_nombre_visible_proveedor

LISTADO_TIMEOUT_SECONDS = 300
LISTADO_TIMEOUT_FOOTER = "Tienes 5 minutos para elegir un experto."


# ==================== FUNCIONES ====================


def _nombre_corto_proveedor(proveedor: Dict[str, Any]) -> str:
    return resolver_nombre_visible_proveedor(
        proveedor,
        status="approved",
        corto=True,
    )


def mensaje_intro_listado_proveedores(ciudad: str) -> str:
    if ciudad:
        return f"*Encontré estas opciones en {ciudad}:*"
    return "*Encontré estas opciones para ti:*"


def _provider_option_id(proveedor: Dict[str, Any], indice: int) -> str:
    provider_id = str(proveedor.get("id") or proveedor.get("provider_id") or "").strip()
    if provider_id:
        return f"provider_select_{provider_id}"
    return f"provider_select_idx_{indice}"


def _descripcion_servicio_proveedor(proveedor: Dict[str, Any]) -> str:
    """Extrae el servicio más relevante del proveedor para mostrar en el listado."""
    servicio = proveedor.get("matched_service_name") or ""
    if servicio:
        return servicio[:72]  # WhatsApp limit: 72 chars para descripción
    return ""


def construir_ui_lista_proveedores(proveedores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construye una lista interactiva de hasta 5 proveedores."""
    opciones: List[Dict[str, Any]] = []
    for indice, proveedor in enumerate(proveedores[:5], start=1):
        opcion = {
            "id": _provider_option_id(proveedor, indice - 1),
            "title": _nombre_corto_proveedor(proveedor)[:24],
        }
        descripcion = _descripcion_servicio_proveedor(proveedor)
        if descripcion:
            opcion["description"] = descripcion
        opciones.append(opcion)

    return {
        "type": "list",
        "id": "provider_results_v1",
        "list_button_text": "Ver expertos",
        "list_section_title": "Expertos disponibles",
        "footer_text": LISTADO_TIMEOUT_FOOTER,
        "options": opciones,
    }


def marcar_ventana_listado_proveedores(
    flujo: Dict[str, Any], ahora: datetime | None = None
) -> None:
    """Guarda el inicio y vencimiento de la ventana exclusiva del listado."""
    ahora_actual = ahora or datetime.utcnow()
    flujo["provider_results_sent_at"] = ahora_actual.isoformat()
    flujo["provider_results_expires_at"] = (
        ahora_actual + timedelta(seconds=LISTADO_TIMEOUT_SECONDS)
    ).isoformat()


def limpiar_ventana_listado_proveedores(flujo: Dict[str, Any]) -> None:
    """Elimina los timestamps del timeout exclusivo del listado."""
    flujo.pop("provider_results_sent_at", None)
    flujo.pop("provider_results_expires_at", None)


def mensaje_timeout_listado_proveedores(ciudad: str = "") -> str:
    _ = ciudad
    return "¿Te ayudo con otro servicio?"


def bloque_listado_proveedores_compacto(proveedores: List[Dict[str, Any]]) -> str:
    """Genera listado de proveedores con números (1-5) y solo nombre."""
    lineas: List[str] = [""]
    for indice, proveedor in enumerate(proveedores[:5], start=1):
        nombre = _nombre_corto_proveedor(proveedor)
        lineas.append(f"*{indice}.* {nombre}")
    lineas.append("")
    return "\n".join(lineas)


def mensaje_listado_sin_resultados(ciudad: str) -> str:
    ciudad_texto = (ciudad or "").strip()
    if ciudad_texto:
        return f"❌ *No* encontré expertos en *{ciudad_texto}*."
    return "❌ *No* encontré expertos."


def instruccion_seleccion_lista() -> str:
    """Instrucción para seleccionar proveedor desde la lista interactiva."""
    return "Selecciona un experto de la lista para ver su perfil."


def resolver_proveedor_desde_lista(
    selected_option: str | None,
    proveedores: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    """Resuelve el proveedor seleccionado desde el id de lista interactiva."""
    selected = (selected_option or "").strip().lower()
    if not selected:
        return None

    for indice, proveedor in enumerate(proveedores[:5], start=1):
        option_id = _provider_option_id(proveedor, indice - 1).lower()
        if selected == option_id:
            return proveedor
    return None


def error_proveedor_no_encontrado() -> str:
    """Error cuando no se encuentra el proveedor seleccionado."""
    return "No encontré ese proveedor, elige otra opción."


def preguntar_servicio() -> str:
    """Pregunta qué servicio necesita."""
    return "Perfecto. Describe el problema o la necesidad que quieres resolver."
