"""Utilidades canónicas para identidad visible de proveedores."""

from __future__ import annotations

from typing import Any, Optional


def limpiar_texto(valor: Optional[str]) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    return texto


def _es_aprobado(valor: Optional[str]) -> bool:
    return limpiar_texto(valor).lower() == "approved"


def _resolver_proveedor_campo(
    proveedor: Any,
    campo: str,
    valor: Optional[str],
) -> Optional[str]:
    if valor is not None:
        return valor
    if proveedor is None:
        return None
    if hasattr(proveedor, "get"):
        return proveedor.get(campo)
    return getattr(proveedor, campo, None)


def _nombre_documental(
    document_first_names: Optional[str],
    document_last_names: Optional[str],
) -> str:
    partes = [
        limpiar_texto(document_first_names),
        limpiar_texto(document_last_names),
    ]
    return " ".join(parte for parte in partes if parte).strip()


def _nombre_visible_legacy(
    display_name: Optional[str],
    formatted_name: Optional[str],
    full_name: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> str:
    for candidato in (
        display_name,
        formatted_name,
        full_name,
        " ".join(
            parte
            for parte in [limpiar_texto(first_name), limpiar_texto(last_name)]
            if parte
        ).strip(),
    ):
        texto = limpiar_texto(candidato)
        if texto:
            return texto
    return ""


def resolver_nombre_corto_proveedor(
    proveedor: Any = None,
    *,
    status: Optional[str] = None,
    display_name: Optional[str] = None,
    document_first_names: Optional[str] = None,
    first_name: Optional[str] = None,
    fallback: str = "Proveedor",
) -> str:
    """Resuelve el nombre corto visible del proveedor."""
    if proveedor is not None:
        status = _resolver_proveedor_campo(proveedor, "status", status)
        display_name = _resolver_proveedor_campo(
            proveedor, "display_name", display_name
        )
        document_first_names = _resolver_proveedor_campo(
            proveedor, "document_first_names", document_first_names
        )
        first_name = _resolver_proveedor_campo(proveedor, "first_name", first_name)

    if _es_aprobado(status):
        nombre_documental = limpiar_texto(document_first_names)
        if nombre_documental:
            return nombre_documental.split()[0]

    nombre_visible = limpiar_texto(display_name) or limpiar_texto(first_name)
    if nombre_visible:
        return nombre_visible.split()[0]

    nombre_documental = limpiar_texto(document_first_names)
    if nombre_documental:
        return nombre_documental.split()[0]

    return fallback


def resolver_nombre_visible_proveedor(
    proveedor: Any = None,
    *,
    status: Optional[str] = None,
    display_name: Optional[str] = None,
    formatted_name: Optional[str] = None,
    full_name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    document_first_names: Optional[str] = None,
    document_last_names: Optional[str] = None,
    fallback: str = "Proveedor",
) -> str:
    """Resuelve el nombre visible completo del proveedor."""
    if proveedor is not None:
        status = _resolver_proveedor_campo(proveedor, "status", status)
        display_name = _resolver_proveedor_campo(
            proveedor, "display_name", display_name
        )
        formatted_name = _resolver_proveedor_campo(
            proveedor, "formatted_name", formatted_name
        )
        full_name = _resolver_proveedor_campo(proveedor, "full_name", full_name)
        first_name = _resolver_proveedor_campo(proveedor, "first_name", first_name)
        last_name = _resolver_proveedor_campo(proveedor, "last_name", last_name)
        document_first_names = _resolver_proveedor_campo(
            proveedor, "document_first_names", document_first_names
        )
        document_last_names = _resolver_proveedor_campo(
            proveedor, "document_last_names", document_last_names
        )

    if _es_aprobado(status):
        nombre_documental = _nombre_documental(
            document_first_names,
            document_last_names,
        )
        if nombre_documental:
            return nombre_documental

    nombre_visible = _nombre_visible_legacy(
        display_name,
        formatted_name,
        full_name,
        first_name,
        last_name,
    )
    if nombre_visible:
        return nombre_visible

    nombre_documental = _nombre_documental(
        document_first_names,
        document_last_names,
    )
    if nombre_documental:
        return nombre_documental

    return fallback
