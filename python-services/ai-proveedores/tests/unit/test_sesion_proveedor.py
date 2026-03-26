import asyncio
import sys
import types
from pathlib import Path
from typing import Any

imghdr_stub: Any = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.onboarding.progress import (  # noqa: E402
    determinar_checkpoint_onboarding,
    es_perfil_onboarding_completo,
    inferir_checkpoint_onboarding_desde_perfil,
)
from services.onboarding.registration.normalizacion import (  # noqa: E402
    garantizar_campos_obligatorios_proveedor,
)
from services.sesion_proveedor import (  # noqa: E402
    manejar_aprobacion_reciente,
    manejar_bloqueo_revision_posterior,
    manejar_estado_inicial,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
)


def test_resolver_estado_registro_pending_mantiene_bloqueo():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-1",
        "full_name": "Proveedor Pendiente",
        "has_consent": True,
        "verified": False,
        "status": "pending",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, False)


def test_resolver_estado_registro_interview_required_aprueba_acceso_basico():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-1b",
        "full_name": "Proveedor En Revision",
        "has_consent": True,
        "verified": False,
        "status": "interview_required",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, True, False)


def test_resolver_estado_registro_approved_basic_habilita_acceso_basico():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-basic",
        "full_name": "Proveedor Basico",
        "has_consent": True,
        "verified": False,
        "status": "approved_basic",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, True, False)


def test_resolver_estado_registro_profile_pending_review_aprueba_acceso_basico():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-review",
        "full_name": "Proveedor Profesional",
        "has_consent": True,
        "verified": False,
        "status": "profile_pending_review",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, True, False)


def test_resolver_estado_registro_rejected_mantiene_bloqueo():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-2",
        "full_name": "Proveedor Rechazado",
        "has_consent": True,
        "verified": False,
        "status": "rejected",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, True)


def test_manejar_estado_inicial_en_revision_devuelve_menu_normal():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor En Revision",
        "provider_id": "prov-menu-limited",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            provider_id="prov-menu-limited",
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=False,
            approved_basic=False,
            telefono="593999111240@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert len(respuesta["messages"]) == 2
    assert "revis" in respuesta["messages"][0]["response"].lower()
    assert (
        "Información personal" in respuesta["messages"][1]["ui"]["options"][0]["title"]
    )


def test_manejar_estado_inicial_rejected_permanece_en_pending_verification():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor Rechazado",
        "provider_id": "prov-rejected",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            provider_id="prov-rejected",
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=False,
            approved_basic=False,
            telefono="593999111241@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert respuesta["messages"]
    assert len(respuesta["messages"]) == 2
    assert "revis" in respuesta["messages"][0]["response"].lower()
    assert respuesta["messages"][1]["ui"]["type"] == "list"


def test_manejar_estado_inicial_approved_basic_muestra_menu_interactivo():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor Basico",
        "approved_basic": True,
        "provider_id": "prov-basic",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            provider_id="prov-basic",
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=True,
            approved_basic=True,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["approved_basic"] is True
    assert respuesta["messages"][0]["response"] == "Elige la opción de interés."
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["id"] == "provider_main_menu_v1"


def test_manejar_estado_inicial_aprobado_muestra_menu_interactivo():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor Aprobado",
        "approved_basic": False,
        "provider_id": "prov-approved",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            provider_id="prov-approved",
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=True,
            approved_basic=False,
            telefono="593999111288@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert (
        respuesta["messages"][0]["ui"]["options"][0]["id"]
        == "provider_menu_info_personal"
    )


def test_manejar_aprobacion_reciente_notifica_una_sola_vez():
    flujo = {
        "state": "pending_verification",
        "full_name": "Proveedor Aprobado",
    }

    primera_respuesta = manejar_aprobacion_reciente(
        flujo=flujo,
        esta_verificado=True,
        approved_basic=False,
    )

    assert primera_respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["verification_notified"] is True
    assert "aprobado" in primera_respuesta["messages"][0]["response"].lower()

    flujo["state"] = "pending_verification"
    segunda_respuesta = manejar_aprobacion_reciente(
        flujo=flujo,
        esta_verificado=True,
        approved_basic=False,
    )

    assert segunda_respuesta is None
    assert flujo["state"] == "awaiting_menu_option"


def test_bloqueo_revision_posterior_limita_respuestas():
    flujo = {
        "state": "pending_verification",
        "full_name": "Proveedor En Revision",
    }

    respuestas = [
        manejar_bloqueo_revision_posterior(
            flujo=flujo,
            perfil_proveedor=None,
            esta_verificado=False,
        )
        for _ in range(4)
    ]

    for respuesta in respuestas[:3]:
        assert respuesta is not None
        assert "en revisión" in respuesta["messages"][0]["response"].lower()

    assert respuestas[3] is not None
    assert respuestas[3]["messages"] == []
    assert flujo["pending_review_attempts"] == 3
    assert flujo["review_silenced"] is True


def test_manejar_bloqueo_revision_posterior_detecta_perfil_completo_pendiente():
    flujo = {"state": None, "full_name": "Proveedor Completo"}
    perfil = {
        "id": "prov-review",
        "full_name": "Proveedor Completo",
        "has_consent": True,
        "verified": False,
        "status": "pending",
        "city": "Quito",
        "dni_front_photo_url": "dni-front.jpg",
        "face_photo_url": "face.jpg",
        "experience_range": "5 a 10 años",
        "services_list": ["Plomería"],
    }

    respuesta = manejar_bloqueo_revision_posterior(
        flujo=flujo,
        perfil_proveedor=perfil,
        esta_verificado=False,
    )

    assert respuesta is not None
    assert flujo["state"] == "pending_verification"
    assert flujo["provider_id"] == "prov-review"
    assert flujo["pending_review_attempts"] == 1
    assert "en revisión" in respuesta["messages"][0]["response"].lower()


def test_sincronizar_flujo_con_perfil_prioriza_datos_durables_sobre_redis():
    flujo = {
        "city": "loja",
        "location_lat": 1.23,
        "location_lng": 4.56,
        "services": ["servicio redis viejo"],
        "real_phone": "0999999999",
    }
    perfil = {
        "id": "prov-55",
        "full_name": "Proveedor Canonico",
        "city": "cuenca",
        "location_lat": -2.9,
        "location_lng": -78.9,
        "location_updated_at": "2026-03-08T15:00:00+00:00",
        "city_confirmed_at": "2026-03-08T15:00:00+00:00",
        "services_list": ["servicio supabase"],
        "generic_services_removed": ["pendiente supabase"],
        "real_phone": "593999111222",
        "experience_years": 3,
        "experience_range": "3 a 5 años",
        "verified": True,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["city"] == "cuenca"
    assert flujo["location_lat"] == -2.9
    assert flujo["location_lng"] == -78.9
    assert flujo["services"] == ["servicio supabase", "pendiente supabase"]
    assert flujo["real_phone"] == "593999111222"
    assert flujo["experience_years"] == 3
    assert flujo["experience_range"] == "3 a 5 años"


def test_sincronizar_flujo_con_perfil_copia_datos_de_identidad():
    flujo = {}
    perfil = {
        "id": "prov-identity",
        "full_name": "Proveedor Identidad",
        "document_first_names": "Ana Maria",
        "document_last_names": "Perez Lopez",
        "document_id_number": "0912345678",
        "services_list": [],
        "verified": True,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["document_first_names"] == "Ana Maria"
    assert flujo["document_last_names"] == "Perez Lopez"
    assert flujo["document_id_number"] == "0912345678"


def test_sincronizar_flujo_con_perfil_copia_checkpoint_onboarding():
    flujo = {}
    perfil = {
        "id": "prov-checkpoint",
        "full_name": "Proveedor Checkpoint",
        "onboarding_step": "onboarding_face_photo",
        "onboarding_step_updated_at": "2026-03-23T12:00:00+00:00",
        "services_list": [],
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["onboarding_step"] == "onboarding_face_photo"
    assert flujo["onboarding_step_updated_at"] == "2026-03-23T12:00:00+00:00"


def test_sincronizar_flujo_con_perfil_reconstruye_checkpoint_legacy_desde_perfil():
    flujo = {}
    perfil = {
        "id": "prov-legacy-checkpoint",
        "full_name": "Proveedor Legacy",
        "city": "Quito",
        "dni_front_photo_url": "dni-front.jpg",
        "face_photo_url": None,
        "onboarding_step": "awaiting_face_photo",
        "services_list": [],
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["onboarding_step"] == "onboarding_face_photo"


def test_checkpoint_onboarding_infiere_desde_perfil_durable():
    perfil = {
        "id": "prov-infer",
        "full_name": "",
        "city": "",
        "dni_front_photo_url": None,
        "face_photo_url": None,
        "experience_range": None,
        "services_list": [],
        "has_consent": False,
        "verified": False,
        "status": "pending",
    }

    assert inferir_checkpoint_onboarding_desde_perfil(perfil) == "onboarding_city"


def test_checkpoint_onboarding_sin_consent_retorna_consentimiento():
    perfil = {
        "id": "prov-consent",
        "full_name": "Proveedor Consentimiento",
        "city": "Quito",
        "dni_front_photo_url": "dni-front.jpg",
        "face_photo_url": "face.jpg",
        "experience_range": "3 a 5 años",
        "services_list": ["Plomeria"],
        "has_consent": False,
        "verified": False,
        "status": "pending",
    }

    assert inferir_checkpoint_onboarding_desde_perfil(perfil) == "onboarding_consent"


def test_checkpoint_onboarding_detecta_perfil_completo():
    perfil = {
        "id": "prov-complete",
        "full_name": "Proveedor Completo",
        "city": "cuenca",
        "dni_front_photo_url": "https://example.com/dni.jpg",
        "face_photo_url": "https://example.com/face.jpg",
        "experience_range": "3 a 5 años",
        "services_list": ["Plomeria"],
        "has_consent": True,
        "verified": False,
        "status": "pending",
    }

    assert es_perfil_onboarding_completo(perfil) is True
    assert inferir_checkpoint_onboarding_desde_perfil(perfil) == "awaiting_menu_option"


def test_checkpoint_onboarding_determina_persistencia_solo_en_onboarding():
    flujo = {
        "state": "viewing_personal_name",
        "provider_id": "prov-checkpoint",
    }

    assert determinar_checkpoint_onboarding(flujo) is None


def test_sincronizar_flujo_con_perfil_marca_approved_basic():
    flujo = {}
    perfil = {
        "id": "prov-basic",
        "full_name": "Proveedor Basico",
        "services_list": [],
        "status": "approved_basic",
        "verified": False,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["approved_basic"] is True


def test_sincronizar_flujo_perfil_pending_review_marca_aprobado_basico():
    flujo = {}
    perfil = {
        "id": "prov-review",
        "full_name": "Proveedor Profesional",
        "services_list": [],
        "status": "profile_pending_review",
        "verified": False,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["approved_basic"] is True
    assert flujo["profile_pending_review"] is False


def test_garantizar_campos_obligatorios_preserva_status_existente():
    perfil = {
        "id": "prov-basic",
        "full_name": "Proveedor Basico",
        "verified": True,
        "status": "approved_basic",
    }

    normalizado = garantizar_campos_obligatorios_proveedor(perfil)

    assert normalizado["status"] == "approved_basic"
