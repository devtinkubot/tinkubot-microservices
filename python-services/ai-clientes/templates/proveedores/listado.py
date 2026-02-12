"""Mensajes relacionados con el listado de proveedores."""

from typing import Any, Dict, List


# ==================== FUNCIONES ====================

def mensaje_intro_listado_proveedores(ciudad: str) -> str:
    if ciudad:
        return f"*Encontré estas opciones en {ciudad}:*"
    return "*Encontré estas opciones para ti:*"


def bloque_listado_proveedores_compacto(proveedores: List[Dict[str, Any]]) -> str:
    """Genera listado de proveedores con números (1-5) y solo nombre."""
    lineas: List[str] = [""]
    for indice, proveedor in enumerate(proveedores[:5], start=1):
        nombre = (
            proveedor.get("name") or proveedor.get("provider_name") or "Proveedor"
        ).strip()
        lineas.append(f"{indice}) {nombre}")
    lineas.append("")
    return "\n".join(lineas)


def mensaje_listado_sin_resultados(ciudad: str) -> str:
    lineas = [
        mensaje_intro_listado_proveedores(ciudad),
        "",
        "    -- No tenemos aún proveedores --",
        "",
    ]
    return "\n".join(lineas)


def instruccion_seleccion_numero() -> str:
    """Instrucción para seleccionar proveedor por número."""
    return "Indica el número (1-5) del proveedor que quieres ver."
def error_proveedor_no_encontrado() -> str:
    """Error cuando no se encuentra el proveedor seleccionado."""
    return "No encontré ese proveedor, elige otra opción."

def preguntar_servicio() -> str:
    """Pregunta qué servicio necesita."""
    return "Perfecto. Describe el problema o la necesidad que quieres resolver."
