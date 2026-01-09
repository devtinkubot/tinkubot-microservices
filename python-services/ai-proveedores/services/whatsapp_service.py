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
        # Sincronizar has_consent si no está en el flow
        if provider_profile.get("has_consent") and not flow.get("has_consent"):
            flow["has_consent"] = True

        # Extraer y sincronizar provider_id
        provider_id = provider_profile.get("id")
        if provider_id:
            flow["provider_id"] = provider_id

        # Extraer y sanitizar services_list desde provider_profile
        servicios_guardados = provider_profile.get("services_list") or []
        flow["services"] = servicios_guardados
    else:
        # Si no hay perfil, inicializar services como lista vacía
        flow.setdefault("services", [])

    # Determinar estado de registro del proveedor
    esta_registrado = determinar_estado_registro_proveedor(provider_profile)
    flow["esta_registrado"] = esta_registrado

    # Persistir el flow actualizado
    await establecer_flujo(phone, flow)

    return flow
