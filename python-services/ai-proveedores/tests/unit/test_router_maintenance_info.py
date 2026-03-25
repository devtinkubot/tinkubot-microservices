import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.maintenance.info as modulo_info  # noqa: E402
from routes.maintenance import (  # noqa: E402
    manejar_informacion_personal_mantenimiento,
    manejar_informacion_profesional_mantenimiento,
)


def test_mantenimiento_info_personal_delega(monkeypatch):
    flujo = {"state": "awaiting_personal_info_action"}
    llamadas = []

    async def _fake_personal(**kwargs):
        llamadas.append(kwargs)
        return {"success": True, "messages": [{"response": "personal"}]}

    monkeypatch.setattr(
        modulo_info,
        "manejar_submenu_informacion_personal",
        _fake_personal,
    )

    resultado = asyncio.run(
        manejar_informacion_personal_mantenimiento(
            flujo=flujo,
            texto_mensaje="nombre",
            opcion_menu="1",
        )
    )

    assert resultado["success"] is True
    assert resultado["messages"][0]["response"] == "personal"
    assert llamadas[0]["flujo"] is flujo


def test_mantenimiento_info_profesional_delega(monkeypatch):
    flujo = {"state": "awaiting_professional_info_action"}
    llamadas = []

    async def _fake_profesional(**kwargs):
        llamadas.append(kwargs)
        return {"success": True, "messages": [{"response": "profesional"}]}

    monkeypatch.setattr(
        modulo_info,
        "manejar_submenu_informacion_profesional",
        _fake_profesional,
    )

    resultado = asyncio.run(
        manejar_informacion_profesional_mantenimiento(
            flujo=flujo,
            texto_mensaje="experiencia",
            opcion_menu="1",
        )
    )

    assert resultado["success"] is True
    assert resultado["messages"][0]["response"] == "profesional"
    assert llamadas[0]["flujo"] is flujo
