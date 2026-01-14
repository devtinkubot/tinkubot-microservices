"""Servicio de gestión de flows de WhatsApp con perfiles de proveedores."""
import logging
from typing import Any, Dict, Optional

from services.flow_service import establecer_flujo
from services.profile_service import determinar_estado_registro_proveedor

logger = logging.getLogger(__name__)


async def inicializar_flow_con_perfil(
    phone: str,
    flow: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
    supabase_client,
) -> Dict[str, Any]:
    """
    Inicializa y sincroniza el flow de WhatsApp con el perfil del proveedor.

    Esta función extrae información relevante del perfil del proveedor y la
    sincroniza con el estado del flow, asegurando que ambos estén alineados.

    Args:
        phone: Número de teléfono del proveedor
        flow: Diccionario con el estado actual del flow
        provider_profile: Perfil del proveedor desde Supabase (puede ser None)
        supabase_client: Cliente de Supabase para persistencia

    Returns:
        Dict con el flow actualizado y sincronizado
    """
    if provider_profile:
        # Extraer y sincronizar provider_id
        provider_id = provider_profile.get("id")
        if provider_id:
            flow["provider_id"] = provider_id

        # Sincronizar has_consent si no está en el flow
        # Importante: Si el proveedor tiene un perfil (tiene id), asumir que ya dio su consentimiento
        has_consent_from_db = provider_profile.get("has_consent")

        if (has_consent_from_db or provider_id) and not flow.get("has_consent"):
            flow["has_consent"] = True

        # Extraer y sanitizar services_list desde provider_profile
        servicios_guardados = provider_profile.get("services_list") or []
        flow["services"] = servicios_guardados
    else:
        # Si no hay perfil, limpiar TODOS los campos relacionados con el perfil
        # Esto es crítico para evitar que se muestre el menú de proveedor registrado
        # después de eliminar el registro
        flow.pop("provider_id", None)
        flow.pop("is_verified", None)
        flow.pop("is_pending_review", None)
        flow.pop("was_pending_review", None)
        flow["esta_registrado"] = False
        flow["services"] = []

    # Determinar estado de registro del proveedor
    esta_registrado = determinar_estado_registro_proveedor(provider_profile)
    flow["esta_registrado"] = esta_registrado

    # Detectar proveedor en estado de revisión pendiente
    # Si el proveedor existe pero no está verificado, está pendiente de revisión
    if provider_profile and provider_profile.get("id"):
        is_verified = bool(provider_profile.get("verified", False))
        if not is_verified:
            # Proveedor existe pero no está verificado → pendiente de revisión
            flow["is_pending_review"] = True
            # Mantener el estado en pending_verification si no está ya definido
            if not flow.get("state") or flow.get("state") not in ["pending_verification", "verified"]:
                flow["state"] = "pending_verification"
        else:
            # Proveedor verificado
            flow["is_verified"] = True
            # Si estaba pendiente, actualizar que ya fue verificado
            if flow.get("was_pending_review"):
                flow["was_pending_review"] = False  # Ya no está pendiente
            # Si no tiene estado o está en pending_verification, moverlo a verified
            if not flow.get("state") or flow.get("state") == "pending_verification":
                flow["state"] = "verified"

    # Persistir el flow actualizado
    await establecer_flujo(phone, flow)

    return flow
