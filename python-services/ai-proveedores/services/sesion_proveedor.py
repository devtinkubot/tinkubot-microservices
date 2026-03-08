"""Reglas de sesión y estado del proveedor."""

from typing import Any, Dict, Optional, Tuple

from flows.consentimiento import solicitar_consentimiento
from flows.constructores import (
    construir_menu_principal,
    construir_respuesta_revision,
    construir_respuesta_revision_con_menu_limitado,
    construir_respuesta_verificado,
)
from flows.registro import determinar_estado_registro

ESTADOS_MENU_LIMITADO = {"interview_required"}
ESTADOS_BLOQUEO_REVISION = {"rejected"}


def normalizar_estado_administrativo(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> str:
    """Normaliza el estado administrativo persistido del proveedor."""
    if not perfil_proveedor:
        return "pending"

    estado_crudo = str(perfil_proveedor.get("status") or "").strip().lower()
    if estado_crudo in {"approved", "aprobado", "ok"}:
        return "approved"
    if estado_crudo in {"rejected", "rechazado", "denied"}:
        return "rejected"
    if estado_crudo in {
        "interview_required",
        "entrevista",
        "auditoria",
        "needs_info",
        "falta_info",
        "faltainfo",
    }:
        return "interview_required"
    if estado_crudo in {"pending", "pendiente", "new"}:
        return "pending"
    return "approved" if perfil_proveedor.get("verified") else "pending"


def perfil_tiene_menu_limitado(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> bool:
    """Indica si el proveedor puede editar perfil sin estar aprobado."""
    if not perfil_proveedor:
        return False
    if perfil_proveedor.get("verified"):
        return False
    if not determinar_estado_registro(perfil_proveedor):
        return False
    return normalizar_estado_administrativo(perfil_proveedor) in ESTADOS_MENU_LIMITADO


def sincronizar_flujo_con_perfil(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Sincroniza datos del flujo con el perfil persistido."""
    if perfil_proveedor:
        if perfil_proveedor.get("has_consent") and not flujo.get("has_consent"):
            flujo["has_consent"] = True
        proveedor_id = perfil_proveedor.get("id")
        if proveedor_id:
            flujo["provider_id"] = proveedor_id
        if perfil_proveedor.get("full_name"):
            flujo["full_name"] = perfil_proveedor.get("full_name")
        servicios_guardados = perfil_proveedor.get("services_list") or []
        flujo["services"] = servicios_guardados
        if perfil_proveedor.get("real_phone") and not flujo.get("real_phone"):
            flujo["real_phone"] = perfil_proveedor.get("real_phone")
        flujo["menu_limitado"] = perfil_tiene_menu_limitado(perfil_proveedor)
    else:
        flujo.setdefault("services", [])
        flujo["menu_limitado"] = False
    return flujo


def resolver_estado_registro(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Tuple[bool, bool, bool, bool]:
    """Calcula flags del estado de registro."""
    tiene_consentimiento = bool(flujo.get("has_consent"))
    esta_registrado = determinar_estado_registro(perfil_proveedor)
    flujo["esta_registrado"] = esta_registrado
    esta_verificado = bool(perfil_proveedor and perfil_proveedor.get("verified"))
    estado_administrativo = normalizar_estado_administrativo(perfil_proveedor)
    esta_pendiente_revision = bool(
        esta_registrado
        and not esta_verificado
        and estado_administrativo in ESTADOS_BLOQUEO_REVISION
    )
    return (
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    )


def manejar_pendiente_revision(
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    esta_pendiente_revision: bool,
) -> Optional[Dict[str, Any]]:
    """Aplica bloqueo por pendiente de revisión."""
    if not esta_pendiente_revision:
        return None
    flujo.update(
        {
            "state": "pending_verification",
            "has_consent": True,
            "provider_id": proveedor_id,
        }
    )
    nombre_proveedor = flujo["full_name"]
    return construir_respuesta_revision(nombre_proveedor)


def manejar_aprobacion_reciente(
    flujo: Dict[str, Any],
    esta_verificado: bool,
) -> Optional[Dict[str, Any]]:
    """Notifica cuando un perfil pasa de pendiente a verificado."""
    if flujo.get("state") != "pending_verification" or not esta_verificado:
        return None
    flujo.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "verification_notified": True,
            "menu_limitado": False,
        }
    )
    return construir_respuesta_verificado()


async def manejar_estado_inicial(
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    esta_verificado: bool,
    menu_limitado: bool,
    telefono: str,
) -> Optional[Dict[str, Any]]:
    """Resuelve la primera interacción cuando no hay estado."""
    if estado:
        return None

    if not tiene_consentimiento:
        nuevo_flujo = {"state": "awaiting_consent", "has_consent": False}
        if not esta_registrado and flujo.get("requires_real_phone"):
            nuevo_flujo["post_consent_state"] = "awaiting_real_phone"
        elif not esta_registrado:
            nuevo_flujo["post_consent_state"] = "awaiting_city"
        flujo.clear()
        flujo.update(nuevo_flujo)
        return await solicitar_consentimiento(telefono)

    if not esta_registrado:
        # NO está registrado: resetear consentimiento y mostrarlo de nuevo
        # (el menú solo se muestra cuando el registro está completo)
        flujo.clear()
        flujo.update({"state": "awaiting_consent", "has_consent": False})
        return await solicitar_consentimiento(telefono)

    if not esta_verificado:
        if menu_limitado:
            flujo.update(
                {
                    "state": "awaiting_menu_option",
                    "has_consent": True,
                    "esta_registrado": True,
                    "menu_limitado": True,
                }
            )
            nombre_proveedor = flujo["full_name"]
            return construir_respuesta_revision_con_menu_limitado(nombre_proveedor)
        flujo.update(
            {
                "state": "pending_verification",
                "has_consent": True,
                "esta_registrado": True,
            }
        )
        nombre_proveedor = flujo["full_name"]
        return construir_respuesta_revision(nombre_proveedor)

    # SÍ está registrado: establecer estado para menú de registrados
    flujo.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "verification_notified": True,
            "menu_limitado": False,
        }
    )
    return {
        "success": True,
        "messages": [{"response": construir_menu_principal(esta_registrado=True)}],
    }
