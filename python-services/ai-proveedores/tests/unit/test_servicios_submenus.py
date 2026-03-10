import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.gestores_estados.gestor_servicios as modulo_gestor_servicios  # noqa: E402
from flows.gestores_estados.gestor_menu import manejar_estado_menu  # noqa: E402
from flows.router import enrutar_estado  # noqa: E402
from flows.gestores_estados.gestor_servicios import (  # noqa: E402
    manejar_accion_servicios,
    manejar_confirmacion_agregar_servicios,
)


def test_selector_servicios_abre_agregado_directo():
    flujo = {"services": ["plomeria"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            opcion_menu="1",
        )
    )

    assert flujo["state"] == "awaiting_service_add"
    assert "nuevo servicio" in respuesta["response"].lower()


def test_selector_servicios_muestra_menu_unificado():
    flujo = {"services": ["plomeria"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="9",
            opcion_menu="9",
        )
    )

    assert "Gestión de Servicios" in respuesta["messages"][1]["response"]
    assert "Agregar servicio" in respuesta["messages"][1]["response"]
    assert "Eliminar servicio" in respuesta["messages"][1]["response"]


def test_confirmacion_agregar_servicios_persiste_y_regresa_a_menu(monkeypatch):
    async def _actualizar_servicios(proveedor_id, servicios):
        return servicios

    monkeypatch.setattr(
        modulo_gestor_servicios,
        "actualizar_servicios",
        _actualizar_servicios,
    )

    flujo = {
        "services": ["desarrollo de software"],
        "service_add_temporales": ["transporte terrestre nacional de carga"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_service_action"
    assert flujo["services"] == [
        "desarrollo de software",
        "transporte terrestre nacional de carga",
    ]
    assert (
        "transporte terrestre nacional de carga" in respuesta["messages"][0]["response"]
    )


def test_confirmacion_agregar_servicios_con_siete_registrados_informa_limite():
    flujo = {
        "services": [f"servicio {idx}" for idx in range(1, 8)],
        "service_add_temporales": ["transporte terrestre nacional de carga"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_service_action"
    assert (
        "ya tienes 7 servicios registrados"
        in respuesta["messages"][0]["response"].lower()
    )
    assert "Gestión de Servicios" in respuesta["messages"][1]["response"]


def test_menu_completar_perfil_abre_flujo_profesional_desde_cero():
    flujo = {"services": [], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="completar perfil",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "awaiting_specialty"
    assert "completar tu perfil profesional" in respuesta["messages"][0]["response"].lower()


def test_menu_completar_perfil_reusa_servicios_existentes():
    flujo = {"services": ["plomeria"], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="completar perfil",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "awaiting_services_confirmation"
    assert "plomeria" in respuesta["messages"][1]["response"].lower()


def test_menu_approved_basic_solo_muestra_opcion_completar_perfil():
    flujo = {"services": [], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="2",
            opcion_menu="2",
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert "Completar perfil profesional" in respuesta["messages"][1]["response"]
    assert "Gestionar servicios" not in respuesta["messages"][1]["response"]


def test_completar_perfil_envia_a_revision_humana(monkeypatch):
    async def _actualizar_perfil_profesional(**kwargs):
        return {"success": True}

    monkeypatch.setattr("flows.router.actualizar_perfil_profesional", _actualizar_perfil_profesional)

    flujo = {
        "state": "awaiting_social_media",
        "approved_basic": True,
        "profile_completion_mode": True,
        "menu_limitado": False,
        "provider_id": "prov-basic",
        "experience_years": 5,
        "servicios_temporales": ["plomeria residencial"],
    }

    respuesta = asyncio.run(
        enrutar_estado(
            estado=flujo["state"],
            flujo=flujo,
            texto_mensaje="omitir",
            carga={},
            telefono="593999111200@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=SimpleNamespace(info=lambda *a, **k: None),
        )
    )

    assert flujo["approved_basic"] is False
    assert flujo["profile_pending_review"] is True
    assert flujo["state"] == "pending_verification"
    assert "revisión" in respuesta["response"]["messages"][1]["response"].lower()
    assert "Completar perfil profesional" not in respuesta["response"]["messages"][1]["response"]
