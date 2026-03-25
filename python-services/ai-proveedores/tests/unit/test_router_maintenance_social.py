import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.maintenance.handlers.social as modulo_social  # noqa: E402


def test_mantenimiento_social_reclama_alias_legacy(monkeypatch):
    flujo = {"state": "awaiting_social_media"}
    llamadas = []

    def _fake_espera_red_social(*args, **kwargs):
        llamadas.append({"args": args, "kwargs": kwargs})
        return {"success": True, "messages": [{"response": "social"}]}

    monkeypatch.setattr(
        modulo_social,
        "manejar_espera_red_social",
        _fake_espera_red_social,
    )

    resultado = asyncio.run(
        modulo_social.manejar_redes_mantenimiento(
            flujo=flujo,
            estado="awaiting_social_media",
            texto_mensaje="facebook",
            carga={"selected_option": None},
            supabase=None,
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert resultado["response"]["messages"][0]["response"] == "social"
    assert llamadas[0]["args"][0] is flujo


def test_mantenimiento_social_update_se_mantiene_en_redes(monkeypatch):
    flujo = {"state": "maintenance_social_facebook_username"}
    llamadas = []

    async def _fake_actualizar_redes_sociales(**kwargs):
        llamadas.append(kwargs)
        return {"success": True, "messages": [{"response": "update"}]}

    monkeypatch.setattr(
        modulo_social,
        "manejar_actualizacion_redes_sociales",
        _fake_actualizar_redes_sociales,
    )

    resultado = asyncio.run(
        modulo_social.manejar_redes_mantenimiento(
            flujo=flujo,
            estado="maintenance_social_facebook_username",
            texto_mensaje="@mi_usuario",
            carga={"selected_option": None},
            supabase=None,
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert resultado["response"]["messages"][0]["response"] == "update"
    assert llamadas[0]["flujo"] is flujo
