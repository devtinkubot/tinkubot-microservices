import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.gestores_estados.gestor_menu import manejar_estado_menu
from flows.router import enrutar_estado
from services.sesion_proveedor import manejar_estado_inicial


def test_manejar_estado_inicial_habilita_menu_limitado_en_interview_required():
    flujo = {"full_name": "Proveedor Test"}

    resultado = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=False,
            menu_limitado=True,
            approved_basic=False,
            telefono="593999111230@s.whatsapp.net",
        )
    )

    assert resultado is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["menu_limitado"] is True
    assert len(resultado["messages"]) == 2
    assert "en revisión" in resultado["messages"][1]["response"].lower()


def test_enrutar_estado_pending_verification_con_menu_limitado_abre_menu():
    flujo = {
        "state": "pending_verification",
        "menu_limitado": True,
        "esta_registrado": True,
    }

    resultado = asyncio.run(
        enrutar_estado(
            estado=flujo.get("state"),
            flujo=flujo,
            texto_mensaje="menu",
            carga={},
            telefono="593999111231@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )

    assert resultado is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert "actualizar tu información" in resultado["response"]["messages"][0][
        "response"
    ].lower()


def test_menu_limitado_no_permite_eliminar_registro():
    flujo = {
        "state": "awaiting_menu_option",
        "menu_limitado": True,
        "has_consent": True,
        "esta_registrado": True,
        "provider_id": "prov-123",
        "services": ["plomeria"],
    }

    resultado = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="eliminar",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=True,
        )
    )

    assert resultado["success"] is True
    assert flujo["state"] == "awaiting_menu_option"
    assert "no reconoc" in resultado["messages"][0]["response"].lower()


def test_menu_approved_basic_opcion_invalida_muestra_error_bien_formado():
    flujo = {
        "state": "awaiting_menu_option",
        "approved_basic": True,
        "has_consent": True,
        "esta_registrado": True,
        "provider_id": "prov-abc",
        "services": [],
        "full_name": "Diego Unkuch Gonzalez",
    }

    resultado = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="menu",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert len(resultado["messages"]) == 2
    assert "no reconoc" in resultado["messages"][0]["response"].lower()
    assert resultado["messages"][1]["ui"]["type"] == "list"
    assert resultado["messages"][1]["ui"]["id"] == "provider_main_menu_v1"
