"""Mensajes relacionados con el listado de proveedores."""

from typing import Any, Dict, List


# ==================== FUNCIONES ====================

def mensaje_intro_listado_proveedores(city: str) -> str:
    if city:
        return f"**Encontré estas opciones en {city}:**"
    return "**Encontré estas opciones para ti:**"


def bloque_listado_proveedores_compacto(providers: List[Dict[str, Any]]) -> str:
    """Genera listado de proveedores con números (1-5) y solo nombre."""
    lines: List[str] = [""]
    for idx, provider in enumerate(providers[:5], start=1):
        name = (
            provider.get("name") or provider.get("provider_name") or "Proveedor"
        ).strip()
        lines.append(f"{idx}) {name}")
    lines.append("")
    return "\n".join(lines)


def mensaje_listado_sin_resultados(city: str) -> str:
    lines = [
        mensaje_intro_listado_proveedores(city),
        "",
        "    -- No tenemos aún proveedores --",
        "",
    ]
    return "\n".join(lines)


def instruccion_seleccion_numero() -> str:
    """Instrucción para seleccionar proveedor por número."""
    return "Indica el número (1-5) del proveedor que quieres ver."

def error_proveedor_no_encontrado() -> str:
    """Error cuando no se encuentra el proveedor seleccionado."""
    return "No encontré ese proveedor, elige otra opción."

def preguntar_servicio() -> str:
    """Pregunta qué servicio necesita."""
    return "Perfecto, ¿qué servicio necesitas?"
