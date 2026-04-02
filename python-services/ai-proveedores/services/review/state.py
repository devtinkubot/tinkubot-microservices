"""Política de revisión y aprobación del proveedor."""

from typing import Any, Dict, Optional, Tuple

from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from services.shared.estados_proveedor import (
    normalizar_estado_administrativo as normalizar_estado_administrativo_comun,
)

from .menu import poner_flujo_en_menu_revision
from .messages import construir_respuesta_revision, construir_respuesta_verificado
from .progress import (
    determinar_estado_registro,
    es_perfil_onboarding_completo,
    resolver_checkpoint_onboarding_desde_perfil,
)

ESTADOS_APROBADOS_OPERATIVOS = {"approved"}
ESTADOS_BLOQUEO_REVISION = {"rejected"}
MAX_INTENTOS_REVISION_SIN_RESPUESTA = 3


def _copiar_campo_si_presente(
    flujo: Dict[str, Any],
    perfil_proveedor: Dict[str, Any],
    origen: str,
    destino: Optional[str] = None,
) -> None:
    """Copia un campo del perfil al flujo cuando el valor existe."""
    valor = perfil_proveedor.get(origen)
    if valor is not None:
        flujo[destino or origen] = valor


def _fusionar_servicios_perfil(perfil_proveedor: Dict[str, Any]) -> list[str]:
    """Combina servicios activos y legados en una lista única sin duplicados."""
    servicios_unificados: list[str] = []
    for servicio in [
        *(perfil_proveedor.get("services_list") or []),
        *(perfil_proveedor.get("generic_services_removed") or []),
    ]:
        texto = str(servicio or "").strip()
        if texto and texto not in servicios_unificados:
            servicios_unificados.append(texto)
    return servicios_unificados


def _sincronizar_campos_base(
    flujo: Dict[str, Any],
    perfil_proveedor: Dict[str, Any],
) -> None:
    """Sincroniza datos básicos e identidad del proveedor."""
    if perfil_proveedor.get("has_consent") and not flujo.get("has_consent"):
        flujo["has_consent"] = True
    proveedor_id = perfil_proveedor.get("id")
    if proveedor_id:
        flujo["provider_id"] = proveedor_id
    _copiar_campo_si_presente(flujo, perfil_proveedor, "status")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "document_first_names")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "document_last_names")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "document_id_number")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "display_name")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "formatted_name")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "first_name")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "last_name")
    flujo["full_name"] = resolver_nombre_visible_proveedor(
        proveedor=flujo,
        fallback="",
    )


def _sincronizar_campos_ubicacion(
    flujo: Dict[str, Any],
    perfil_proveedor: Dict[str, Any],
) -> None:
    """Sincroniza los datos de ubicación y confirmación de ciudad."""
    _copiar_campo_si_presente(flujo, perfil_proveedor, "city")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "location_lat")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "location_lng")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "location_updated_at")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "city_confirmed_at")


def _sincronizar_campos_onboarding(
    flujo: Dict[str, Any],
    perfil_proveedor: Dict[str, Any],
) -> None:
    """Sincroniza checkpoints y progreso de onboarding."""
    if perfil_proveedor.get("onboarding_step") is not None:
        flujo["onboarding_step"] = resolver_checkpoint_onboarding_desde_perfil(
            perfil_proveedor
        )
    _copiar_campo_si_presente(
        flujo,
        perfil_proveedor,
        "onboarding_step_updated_at",
    )
    _copiar_campo_si_presente(flujo, perfil_proveedor, "onboarding_complete")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "experience_range")


def _sincronizar_campos_contacto(
    flujo: Dict[str, Any],
    perfil_proveedor: Dict[str, Any],
) -> None:
    """Sincroniza datos de contacto, medios y documentos."""
    flujo["services"] = _fusionar_servicios_perfil(perfil_proveedor)
    redes = _resolver_redes_sociales_local(perfil_proveedor)
    flujo["facebook_username"] = redes["facebook_username"]
    flujo["instagram_username"] = redes["instagram_username"]
    _copiar_campo_si_presente(flujo, perfil_proveedor, "face_photo_url")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "dni_front_photo_url")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "dni_back_photo_url")
    _copiar_campo_si_presente(flujo, perfil_proveedor, "real_phone")


def normalizar_estado_administrativo(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> str:
    """Normaliza el estado administrativo persistido del proveedor."""
    return normalizar_estado_administrativo_comun(perfil_proveedor)


def _resolver_redes_sociales_local(
    datos: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    facebook_username = str(datos.get("facebook_username") or "").strip() or None
    instagram_username = str(datos.get("instagram_username") or "").strip() or None
    return {
        "facebook_username": facebook_username,
        "instagram_username": instagram_username,
    }


def sincronizar_flujo_con_perfil(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Sincroniza datos del flujo con el perfil persistido."""
    if perfil_proveedor:
        _sincronizar_campos_base(flujo, perfil_proveedor)
        _sincronizar_campos_ubicacion(flujo, perfil_proveedor)
        _sincronizar_campos_onboarding(flujo, perfil_proveedor)
        _sincronizar_campos_contacto(flujo, perfil_proveedor)
    else:
        flujo.setdefault("services", [])
        flujo.setdefault("experience_range", None)
        flujo.setdefault("location_updated_at", None)
        flujo.setdefault("city_confirmed_at", None)
        flujo.setdefault("onboarding_step", None)
        flujo.setdefault("onboarding_step_updated_at", None)
    return flujo


def resolver_estado_registro(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Tuple[bool, bool, bool, bool]:
    """Calcula flags del estado de registro."""
    tiene_consentimiento = bool(
        flujo.get("has_consent") or (perfil_proveedor or {}).get("has_consent")
    )
    esta_registrado = bool(determinar_estado_registro(perfil_proveedor))
    flujo["esta_registrado"] = esta_registrado
    estado_administrativo = normalizar_estado_administrativo(perfil_proveedor)
    esta_verificado = estado_administrativo in ESTADOS_APROBADOS_OPERATIVOS
    onboarding_complete = bool((perfil_proveedor or {}).get("onboarding_complete"))
    esta_pendiente_revision = bool(
        esta_registrado
        and not esta_verificado
        and (estado_administrativo in ESTADOS_BLOQUEO_REVISION or onboarding_complete)
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
    nombre_proveedor = resolver_nombre_visible_proveedor(
        proveedor=flujo,
    )
    return construir_respuesta_revision(nombre_proveedor)


def manejar_aprobacion_reciente(
    flujo: Dict[str, Any],
    esta_verificado: bool,
) -> Optional[Dict[str, Any]]:
    """Notifica cuando un perfil pasa de pendiente a verificado."""
    if flujo.get("state") != "pending_verification" or not esta_verificado:
        return None
    if flujo.get("verification_notified"):
        poner_flujo_en_menu_revision(flujo, verification_notified=True)
        return None
    poner_flujo_en_menu_revision(flujo, verification_notified=True)
    return construir_respuesta_verificado()


def _perfil_sigue_en_revision(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> bool:
    """Indica si el proveedor sigue en revisión administrativa."""
    if flujo.get("state") == "pending_verification":
        return True
    if not perfil_proveedor:
        return False

    estado_administrativo = normalizar_estado_administrativo(perfil_proveedor)
    if estado_administrativo != "pending":
        return False

    return es_perfil_onboarding_completo(perfil_proveedor)


def manejar_bloqueo_revision_posterior(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    *,
    esta_verificado: bool,
) -> Optional[Dict[str, Any]]:
    """Mantiene el estado de revisión activo y silencia tras varios intentos."""
    if esta_verificado:
        flujo["pending_review_attempts"] = 0
        flujo["review_silenced"] = False
        return None

    if not _perfil_sigue_en_revision(flujo, perfil_proveedor):
        return None

    intentos_previos = int(flujo.get("pending_review_attempts") or 0)
    flujo["state"] = "pending_verification"
    flujo["has_consent"] = True
    if perfil_proveedor and perfil_proveedor.get("id"):
        flujo["provider_id"] = perfil_proveedor.get("id")

    if intentos_previos >= MAX_INTENTOS_REVISION_SIN_RESPUESTA:
        flujo["review_silenced"] = True
        return {"success": True, "messages": []}

    flujo["pending_review_attempts"] = intentos_previos + 1
    flujo["review_silenced"] = False
    nombre_proveedor = resolver_nombre_visible_proveedor(
        proveedor=flujo,
    )
    return construir_respuesta_revision(nombre_proveedor)
