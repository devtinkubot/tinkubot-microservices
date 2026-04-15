"""Punto de entrada del contexto review."""

from typing import Any, Dict, Optional

from services.review.menu import poner_flujo_en_menu_revision
from services.review.messages import (
    construir_respuesta_revision_con_menu,
)
from services.review.progress import (
    ESTADO_REVISION_PENDIENTE,
    normalizar_checkpoint_onboarding,
)
from services.review.state import (
    manejar_aprobacion_reciente,
    manejar_bloqueo_revision_posterior,
    manejar_pendiente_revision,
    resolver_estado_registro,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
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

    estado_actual = normalizar_checkpoint_onboarding(flujo.get("state")) or ""
    if estado_actual == ESTADO_REVISION_PENDIENTE:
        flujo["state"] = ESTADO_REVISION_PENDIENTE

    if estado_actual == ESTADO_REVISION_PENDIENTE and esta_verificado:
        respuesta_verificacion = manejar_aprobacion_reciente(
            flujo,
            esta_verificado,
        )
        if respuesta_verificacion:
            return respuesta_verificacion

    if estado_actual == ESTADO_REVISION_PENDIENTE or esta_pendiente_revision:
        respuesta_pendiente = manejar_pendiente_revision(
            flujo,
            provider_id,
            True,
        )
        if respuesta_pendiente:
            return respuesta_pendiente

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
        }
    )
    nombre_proveedor = resolver_nombre_visible_proveedor(proveedor=flujo)
    return construir_respuesta_revision_con_menu(nombre_proveedor)
