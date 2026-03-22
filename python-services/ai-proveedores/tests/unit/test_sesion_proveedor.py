import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.sesion_proveedor import (  # noqa: E402
    manejar_aprobacion_reciente,
    manejar_estado_inicial,
    perfil_tiene_menu_limitado,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
)
from services.registro.normalizacion import (  # noqa: E402
    garantizar_campos_obligatorios_proveedor,
)


def test_resolver_estado_registro_pending_no_habilita_menu_limitado():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-1",
        "full_name": "Proveedor Pendiente",
        "verified": False,
        "status": "pending",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, False)
    assert perfil_tiene_menu_limitado(perfil) is False


def test_resolver_estado_registro_interview_required_habilita_menu_limitado():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-1b",
        "full_name": "Proveedor En Revision",
        "verified": False,
        "status": "interview_required",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, False)
    assert perfil_tiene_menu_limitado(perfil) is True


def test_resolver_estado_registro_approved_basic_habilita_acceso_sin_menu_limitado():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-basic",
        "full_name": "Proveedor Basico",
        "verified": False,
        "status": "approved_basic",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, True, False)
    assert perfil_tiene_menu_limitado(perfil) is False


def test_resolver_estado_registro_profile_pending_review_mantiene_revision():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-review",
        "full_name": "Proveedor Profesional",
        "verified": False,
        "status": "profile_pending_review",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, True)
    assert perfil_tiene_menu_limitado(perfil) is False


def test_resolver_estado_registro_rejected_mantiene_bloqueo():
    flujo = {"has_consent": True}
    perfil = {
        "id": "prov-2",
        "full_name": "Proveedor Rechazado",
        "verified": False,
        "status": "rejected",
    }

    resultado = resolver_estado_registro(flujo, perfil)

    assert resultado == (True, True, False, True)
    assert perfil_tiene_menu_limitado(perfil) is False


def test_manejar_estado_inicial_interview_required_devuelve_revision_con_menu_limitado():  # noqa: E501
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor En Revision",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=False,
            menu_limitado=True,
            approved_basic=False,
            telefono="593999111240@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["menu_limitado"] is True
    assert len(respuesta["messages"]) == 2
    assert "revis" in respuesta["messages"][0]["response"].lower()
    assert "Gestionar servicios" in respuesta["messages"][1]["response"]
    assert "Eliminar mi registro" not in respuesta["messages"][1]["response"]


def test_manejar_estado_inicial_rejected_permanece_en_pending_verification():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor Rechazado",
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=False,
            menu_limitado=False,
            approved_basic=False,
            telefono="593999111241@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "pending_verification"
    assert respuesta["messages"]
    assert len(respuesta["messages"]) == 1
    assert "revis" in respuesta["messages"][0]["response"].lower()


def test_manejar_estado_inicial_approved_basic_muestra_menu_interactivo():
    flujo = {
        "has_consent": True,
        "full_name": "Proveedor Basico",
        "approved_basic": True,
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=True,
            menu_limitado=False,
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
    }

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=True,
            menu_limitado=False,
            approved_basic=False,
            telefono="593999111288@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == "provider_menu_info_personal"


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
        "verified": True,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["city"] == "cuenca"
    assert flujo["location_lat"] == -2.9
    assert flujo["location_lng"] == -78.9
    assert flujo["services"] == ["servicio supabase", "pendiente supabase"]
    assert flujo["real_phone"] == "593999111222"


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


def test_sincronizar_flujo_con_perfil_marca_profile_pending_review():
    flujo = {}
    perfil = {
        "id": "prov-review",
        "full_name": "Proveedor Profesional",
        "services_list": [],
        "status": "profile_pending_review",
        "verified": False,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["profile_pending_review"] is True


def test_garantizar_campos_obligatorios_preserva_status_existente():
    perfil = {
        "id": "prov-basic",
        "full_name": "Proveedor Basico",
        "verified": True,
        "status": "approved_basic",
    }

    normalizado = garantizar_campos_obligatorios_proveedor(perfil)

    assert normalizado["status"] == "approved_basic"
