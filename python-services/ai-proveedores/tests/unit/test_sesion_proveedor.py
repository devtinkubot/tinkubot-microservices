import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.sesion_proveedor import (
    manejar_estado_inicial,
    perfil_tiene_menu_limitado,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
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


def test_manejar_estado_inicial_interview_required_devuelve_revision_con_menu_limitado():
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
            telefono="593999111241@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "pending_verification"
    assert respuesta["messages"]
    assert len(respuesta["messages"]) == 1
    assert "revis" in respuesta["messages"][0]["response"].lower()


def test_sincronizar_flujo_con_perfil_prioriza_datos_durables_sobre_redis():
    flujo = {
        "city": "loja",
        "location_lat": 1.23,
        "location_lng": 4.56,
        "services": ["servicio redis viejo"],
        "generic_services_removed": ["pendiente redis viejo"],
        "service_review_required": False,
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
        "service_review_required": True,
        "real_phone": "593999111222",
        "verified": True,
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["city"] == "cuenca"
    assert flujo["location_lat"] == -2.9
    assert flujo["location_lng"] == -78.9
    assert flujo["services"] == ["servicio supabase"]
    assert flujo["generic_services_removed"] == ["pendiente supabase"]
    assert flujo["service_review_required"] is True
    assert flujo["real_phone"] == "593999111222"
