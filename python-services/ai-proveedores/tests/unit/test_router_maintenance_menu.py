import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.maintenance.router as modulo_router  # noqa: E402


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
