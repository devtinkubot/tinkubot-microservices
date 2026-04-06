import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.maintenance.router as modulo_router  # noqa: E402
import flows.maintenance.menu as modulo_menu  # noqa: E402


def test_menu_mantenimiento_solo_atiende_registrados(monkeypatch):
    flujo = {"state": "awaiting_menu_option"}

    async def _fake_manejar_estado_menu(**kwargs):
        assert kwargs["esta_registrado"] is True
        kwargs["flujo"]["state"] = "awaiting_menu_option"
        return {"success": True, "messages": [{"response": "ok"}]}

    monkeypatch.setattr(modulo_router, "manejar_estado_menu", _fake_manejar_estado_menu)

    resultado = asyncio.run(
        modulo_router.manejar_menu_proveedor(
            flujo=flujo,
            estado="awaiting_menu_option",
            texto_mensaje="menu",
            opcion_menu=None,
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_menu_option"
    assert resultado["response"]["messages"][0]["response"] == "ok"


def test_menu_mantenimiento_no_reclama_no_registrados():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_router.manejar_menu_proveedor(
            flujo=flujo,
            estado="awaiting_menu_option",
            texto_mensaje="menu",
            opcion_menu=None,
            esta_registrado=False,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado is None
    assert flujo["state"] == "awaiting_menu_option"


def test_menu_principal_texto_libre_reenvia_botones():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_menu.manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="hola",
            opcion_menu=None,
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado["success"] is True
    assert resultado["messages"][0]["ui"]["id"] == "provider_main_menu_v1"
    ids = [opcion["id"] for opcion in resultado["messages"][0]["ui"]["options"]]
    assert "provider_menu_completar_perfil" not in ids


def test_menu_principal_acepta_selected_option_de_legado():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_router.manejar_menu_proveedor(
            flujo=flujo,
            estado="awaiting_menu_option",
            texto_mensaje="provider_menu_info_personal",
            opcion_menu=None,
            selected_option="provider_menu_info_personal",
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_personal_info_action"
    assert resultado["response"]["messages"][0]["ui"]["id"] == "provider_personal_info_menu_v1"


def test_menu_principal_acepta_selected_option_profesional():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_router.manejar_menu_proveedor(
            flujo=flujo,
            estado="awaiting_menu_option",
            texto_mensaje="provider_menu_info_profesional",
            opcion_menu=None,
            selected_option="provider_menu_info_profesional",
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_professional_info_action"
    assert (
        resultado["response"]["messages"][0]["ui"]["id"]
        == "provider_professional_info_menu_v1"
    )


def test_menu_principal_acepta_texto_libre_personal():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_menu.manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="informacion personal",
            opcion_menu=None,
            selected_option=None,
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert flujo["state"] == "awaiting_personal_info_action"
    assert resultado["messages"][0]["ui"]["id"] == "provider_personal_info_menu_v1"


def test_menu_principal_acepta_texto_libre_profesional():
    flujo = {"state": "awaiting_menu_option"}

    resultado = asyncio.run(
        modulo_menu.manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="informacion profesional",
            opcion_menu=None,
            selected_option=None,
            esta_registrado=True,
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert flujo["state"] == "awaiting_professional_info_action"
    assert resultado["messages"][0]["ui"]["id"] == "provider_professional_info_menu_v1"
