"""Utilidades de identidad visible para proveedores en ai-clientes."""

from __future__ import annotations

from typing import Any, Optional


def _texto_limpio(valor: Any) -> str:
    return " ".join(str(valor or "").split()).strip()


def _es_aprobado(valor: Optional[str]) -> bool:
    return _texto_limpio(valor).lower() == "approved"


def _extraer(proveedor: Optional[dict[str, Any]], campo: str, valor: Any) -> Any:
    if valor is not None:
        return valor
    if proveedor is None:
        return None
    if hasattr(proveedor, "get"):
        return proveedor.get(campo)
    return getattr(proveedor, campo, None)


def _nombre_documental(
    document_first_names: Any = None,
    document_last_names: Any = None,
) -> str:
    nombres = _texto_limpio(document_first_names)
    apellidos = _texto_limpio(document_last_names)
    if nombres and apellidos:
        return f"{nombres} {apellidos}"
    if nombres:
        return nombres
    if apellidos:
        return apellidos
    return ""


def _nombre_visible_legacy(
    display_name: Any = None,
    formatted_name: Any = None,
    full_name: Any = None,
    first_name: Any = None,
    last_name: Any = None,
) -> str:
    candidatos = (
        display_name,
        formatted_name,
        full_name,
        " ".join(
            parte
            for parte in [_texto_limpio(first_name), _texto_limpio(last_name)]
            if parte
        ).strip(),
    )
    for candidato in candidatos:
        texto = _texto_limpio(candidato)
        if texto:
            return texto
    return ""


def resolver_nombre_visible_proveedor(
    proveedor: Optional[dict[str, Any]] = None,
    *,
    status: Optional[str] = None,
    display_name: Optional[str] = None,
    formatted_name: Optional[str] = None,
    full_name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    document_first_names: Optional[str] = None,
    document_last_names: Optional[str] = None,
    corto: bool = False,
    fallback: str = "Proveedor",
) -> str:
    if proveedor is not None:
        status = _extraer(proveedor, "status", status)
        display_name = _extraer(proveedor, "display_name", display_name)
        formatted_name = _extraer(proveedor, "formatted_name", formatted_name)
        full_name = _extraer(proveedor, "full_name", full_name)
        first_name = _extraer(proveedor, "first_name", first_name)
        last_name = _extraer(proveedor, "last_name", last_name)
        document_first_names = _extraer(
            proveedor, "document_first_names", document_first_names
        )
        document_last_names = _extraer(
            proveedor, "document_last_names", document_last_names
        )

    if _es_aprobado(status):
        nombre_documental = _nombre_documental(
            document_first_names,
            document_last_names,
        )
        if nombre_documental:
            return nombre_documental.split()[0] if corto else nombre_documental

    nombre_visible = _nombre_visible_legacy(
        display_name,
        formatted_name,
        full_name,
        first_name,
        last_name,
    )
    if nombre_visible:
        return nombre_visible.split()[0] if corto else nombre_visible

    nombre_documental = _nombre_documental(
        document_first_names,
        document_last_names,
    )
    if nombre_documental:
        return nombre_documental.split()[0] if corto else nombre_documental

    return fallback


def resolver_nombre_corto_proveedor(
    proveedor: Optional[dict[str, Any]] = None,
    *,
    status: Optional[str] = None,
    display_name: Optional[str] = None,
    document_first_names: Optional[str] = None,
    first_name: Optional[str] = None,
    fallback: str = "Proveedor",
) -> str:
    return resolver_nombre_visible_proveedor(
        proveedor,
        status=status,
        display_name=display_name,
        document_first_names=document_first_names,
        first_name=first_name,
        corto=True,
        fallback=fallback,
    )
