"""Política de revisión y aprobación del proveedor."""

from typing import Any, Dict, Optional, Tuple

from services.onboarding.registration import determinar_estado_registro
from services.onboarding.progress import (
    es_perfil_onboarding_completo,
    resolver_checkpoint_onboarding_desde_perfil,
)
from services.maintenance.redes_sociales_slots import resolver_redes_sociales

from .messages import (
    construir_respuesta_revision,
    construir_respuesta_verificado,
)

ESTADOS_APROBADOS_OPERATIVOS = {"approved", "approved_basic"}
ESTADOS_BLOQUEO_REVISION = {"rejected"}
MAX_INTENTOS_REVISION_SIN_RESPUESTA = 3


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


def normalizar_estado_administrativo(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> str:
    """Normaliza el estado administrativo persistido del proveedor."""
    if not perfil_proveedor:
        return "pending"

    estado_crudo = str(perfil_proveedor.get("status") or "").strip().lower()
    if estado_crudo in {"approved_basic", "aprobado_basico", "basic_approved"}:
        return "approved_basic"
    if estado_crudo in {
        "profile_pending_review",
        "perfil_pendiente_revision",
        "professional_review_pending",
        "interview_required",
        "entrevista",
        "auditoria",
        "needs_info",
        "falta_info",
        "faltainfo",
    }:
        return "approved_basic"
    if estado_crudo in {"approved", "aprobado", "ok"}:
        return "approved"
    if estado_crudo in {"rejected", "rechazado", "denied"}:
        return "rejected"
    if estado_crudo in {"pending", "pendiente", "new"}:
        return "pending"
    return "approved" if perfil_proveedor.get("verified") else "pending"


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
        if perfil_proveedor.get("document_first_names") is not None:
            flujo["document_first_names"] = perfil_proveedor.get(
                "document_first_names"
            )
        if perfil_proveedor.get("document_last_names") is not None:
            flujo["document_last_names"] = perfil_proveedor.get("document_last_names")
        if perfil_proveedor.get("document_id_number") is not None:
            flujo["document_id_number"] = perfil_proveedor.get("document_id_number")
        if perfil_proveedor.get("city") is not None:
            flujo["city"] = perfil_proveedor.get("city")
        if perfil_proveedor.get("location_lat") is not None:
            flujo["location_lat"] = perfil_proveedor.get("location_lat")
        if perfil_proveedor.get("location_lng") is not None:
            flujo["location_lng"] = perfil_proveedor.get("location_lng")
        if perfil_proveedor.get("location_updated_at") is not None:
            flujo["location_updated_at"] = perfil_proveedor.get("location_updated_at")
        if perfil_proveedor.get("city_confirmed_at") is not None:
            flujo["city_confirmed_at"] = perfil_proveedor.get("city_confirmed_at")
        if perfil_proveedor.get("onboarding_step") is not None:
            flujo["onboarding_step"] = resolver_checkpoint_onboarding_desde_perfil(
                perfil_proveedor
            )
        if perfil_proveedor.get("onboarding_step_updated_at") is not None:
            flujo["onboarding_step_updated_at"] = perfil_proveedor.get(
                "onboarding_step_updated_at"
            )
        if perfil_proveedor.get("experience_years") is not None:
            flujo["experience_years"] = perfil_proveedor.get("experience_years")
        if perfil_proveedor.get("experience_range") is not None:
            flujo["experience_range"] = perfil_proveedor.get("experience_range")
        flujo["services"] = _fusionar_servicios_perfil(perfil_proveedor)
        if perfil_proveedor.get("social_media_url") is not None:
            flujo["social_media_url"] = perfil_proveedor.get("social_media_url")
        if perfil_proveedor.get("social_media_type") is not None:
            flujo["social_media_type"] = perfil_proveedor.get("social_media_type")
        redes = resolver_redes_sociales(perfil_proveedor)
        flujo["facebook_username"] = redes["facebook_username"]
        flujo["instagram_username"] = redes["instagram_username"]
        if perfil_proveedor.get("face_photo_url") is not None:
            flujo["face_photo_url"] = perfil_proveedor.get("face_photo_url")
        if perfil_proveedor.get("dni_front_photo_url") is not None:
            flujo["dni_front_photo_url"] = perfil_proveedor.get("dni_front_photo_url")
        if perfil_proveedor.get("dni_back_photo_url") is not None:
            flujo["dni_back_photo_url"] = perfil_proveedor.get("dni_back_photo_url")
        if perfil_proveedor.get("real_phone") is not None:
            flujo["real_phone"] = perfil_proveedor.get("real_phone")
        flujo["approved_basic"] = normalizar_estado_administrativo(
            perfil_proveedor
        ) in {"approved_basic", "approved"}
        flujo["profile_pending_review"] = False
    else:
        flujo.setdefault("services", [])
        flujo.setdefault("experience_range", None)
        flujo.setdefault("location_updated_at", None)
        flujo.setdefault("city_confirmed_at", None)
        flujo.setdefault("onboarding_step", None)
        flujo.setdefault("onboarding_step_updated_at", None)
        flujo["approved_basic"] = False
        flujo["profile_pending_review"] = False
    return flujo


def resolver_estado_registro(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Tuple[bool, bool, bool, bool]:
    """Calcula flags del estado de registro."""
    tiene_consentimiento = bool(
        flujo.get("has_consent") or (perfil_proveedor or {}).get("has_consent")
    )
    esta_registrado = bool(
        determinar_estado_registro(perfil_proveedor)
        or (
            perfil_proveedor
            and perfil_proveedor.get("id")
            and perfil_proveedor.get("full_name")
            and tiene_consentimiento
        )
    )
    flujo["esta_registrado"] = esta_registrado
    estado_administrativo = normalizar_estado_administrativo(perfil_proveedor)
    esta_verificado = estado_administrativo in ESTADOS_APROBADOS_OPERATIVOS
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
    approved_basic: bool = False,
) -> Optional[Dict[str, Any]]:
    """Notifica cuando un perfil pasa de pendiente a verificado."""
    if flujo.get("state") != "pending_verification" or not esta_verificado:
        return None
    if flujo.get("verification_notified"):
        flujo.update(
            {
                "state": "awaiting_menu_option",
                "has_consent": True,
                "esta_registrado": True,
                "approved_basic": approved_basic,
                "profile_pending_review": False,
                "pending_review_attempts": 0,
                "review_silenced": False,
            }
        )
        return None
    flujo.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "verification_notified": True,
            "approved_basic": approved_basic,
            "profile_pending_review": False,
            "pending_review_attempts": 0,
            "review_silenced": False,
        }
    )
    return construir_respuesta_verificado(approved_basic=approved_basic)


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
    nombre_proveedor = str(flujo.get("full_name") or "")
    return construir_respuesta_revision(nombre_proveedor)
