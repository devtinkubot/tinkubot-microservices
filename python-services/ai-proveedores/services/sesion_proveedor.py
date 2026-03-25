"""Reglas de sesión y estado del proveedor."""

from typing import Any, Dict, Optional

from flows.constructores import (
    construir_payload_menu_principal,
    construir_respuesta_solicitud_consentimiento,
)
from routes.review.router import manejar_estado_revision_inicial
from services.review.state import (
    manejar_aprobacion_reciente as _manejar_aprobacion_reciente,
    manejar_bloqueo_revision_posterior as _manejar_bloqueo_revision_posterior,
    manejar_pendiente_revision as _manejar_pendiente_revision,
    normalizar_estado_administrativo as _normalizar_estado_administrativo,
    resolver_estado_registro as _resolver_estado_registro,
    sincronizar_flujo_con_perfil as _sincronizar_flujo_con_perfil,
)
from templates.onboarding.consentimiento import payload_consentimiento_proveedor


def normalizar_estado_administrativo(perfil_proveedor: Optional[Dict[str, Any]]) -> str:
    return _normalizar_estado_administrativo(perfil_proveedor)
def sincronizar_flujo_con_perfil(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return _sincronizar_flujo_con_perfil(flujo, perfil_proveedor)


def resolver_estado_registro(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
):
    return _resolver_estado_registro(flujo, perfil_proveedor)


def manejar_pendiente_revision(
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    esta_pendiente_revision: bool,
):
    return _manejar_pendiente_revision(
        flujo,
        proveedor_id,
        esta_pendiente_revision,
    )


def manejar_aprobacion_reciente(
    flujo: Dict[str, Any],
    esta_verificado: bool,
    approved_basic: bool = False,
):
    return _manejar_aprobacion_reciente(
        flujo,
        esta_verificado,
        approved_basic=approved_basic,
    )


def manejar_bloqueo_revision_posterior(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    *,
    esta_verificado: bool,
):
    return _manejar_bloqueo_revision_posterior(
        flujo,
        perfil_proveedor,
        esta_verificado=esta_verificado,
    )


async def manejar_estado_inicial(
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]] = None,
    provider_id: Optional[str] = None,
    tiene_consentimiento: bool,
    esta_registrado: bool,
    esta_verificado: bool,
    approved_basic: bool,
    telefono: str,
) -> Optional[Dict[str, Any]]:
    """Resuelve la primera interacción cuando no hay estado."""
    if not provider_id and not estado:
        flujo.clear()
        flujo.update(
            {
                "state": "onboarding_consent",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return construir_respuesta_solicitud_consentimiento()

    if estado:
        return None

    if not tiene_consentimiento:
        if not esta_registrado:
            flujo.clear()
            flujo.update(
                {
                    "state": "onboarding_consent",
                    "mode": "registration",
                    "has_consent": False,
                }
            )
            return construir_respuesta_solicitud_consentimiento()

        nuevo_flujo = {"state": "onboarding_consent", "has_consent": False}
        flujo.clear()
        flujo.update(nuevo_flujo)
        return construir_respuesta_solicitud_consentimiento()

    if not esta_registrado:
        flujo.clear()
        flujo.update(
            {
                "state": "awaiting_menu_option",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return {
            "success": True,
            "messages": [payload_consentimiento_proveedor()["messages"][0]],
        }

    if not esta_verificado:
        return manejar_estado_revision_inicial(
            flujo=flujo,
            provider_id=provider_id,
        )

    # SÍ está registrado: establecer estado para menú de registrados
    flujo.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "verification_notified": True,
            "approved_basic": approved_basic,
            "profile_pending_review": False,
        }
    )
    return {
        "success": True,
        "messages": [
            construir_payload_menu_principal(
                esta_registrado=True,
                approved_basic=approved_basic,
            )
        ],
    }
