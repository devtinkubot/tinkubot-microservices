"""Punto de entrada del contexto review."""

from typing import Any, Dict, Optional

from services.review.menu import poner_flujo_en_menu_revision
from services.review.messages import (
    construir_respuesta_revision_con_menu,
)
from services.review.state import (
    manejar_aprobacion_reciente,
    manejar_bloqueo_revision_posterior,
    manejar_pendiente_revision,
    resolver_estado_registro,
)


def _marcar_menu_revision(
    flujo: Dict[str, Any],
) -> None:
    poner_flujo_en_menu_revision(flujo)


def manejar_contexto_revision(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    provider_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Resuelve la respuesta de review para el flujo actual."""
    _, _, esta_verificado, esta_pendiente_revision = resolver_estado_registro(
        flujo, perfil_proveedor
    )

    estado_actual = str(flujo.get("state") or "").strip()
    if estado_actual == "pending_verification":
        _marcar_menu_revision(flujo)
        nombre_proveedor = str(flujo.get("full_name") or "")
        return construir_respuesta_revision_con_menu(nombre_proveedor)

    es_pendiente = esta_pendiente_revision or (
        estado_actual == "pending_verification" and not esta_verificado
    )

    if es_pendiente:
        respuesta_pendiente = manejar_pendiente_revision(
            flujo, provider_id, esta_pendiente_revision
        )
        if respuesta_pendiente:
            return respuesta_pendiente

    if estado_actual == "pending_verification" and esta_verificado:
        respuesta_verificacion = manejar_aprobacion_reciente(
            flujo,
            esta_verificado,
        )
        if respuesta_verificacion:
            return respuesta_verificacion

    return manejar_bloqueo_revision_posterior(
        flujo,
        perfil_proveedor,
        esta_verificado=esta_verificado,
    )


def manejar_revision_proveedor(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    provider_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Compatibilidad con la API previa de review."""
    return manejar_contexto_revision(
        flujo=flujo,
        perfil_proveedor=perfil_proveedor,
        provider_id=provider_id,
    )


def manejar_estado_revision_inicial(
    flujo: Dict[str, Any],
    provider_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Entrada de review para estados vacíos o de rehidratación inicial."""
    _marcar_menu_revision(flujo)
    flujo.update(
        {
            "provider_id": provider_id,
            "profile_pending_review": False,
        }
    )
    nombre_proveedor = str(flujo.get("full_name") or "")
    return construir_respuesta_revision_con_menu(nombre_proveedor)
