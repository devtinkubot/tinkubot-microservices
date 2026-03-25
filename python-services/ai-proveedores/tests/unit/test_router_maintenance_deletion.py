import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.maintenance.deletion as modulo_deletion  # noqa: E402
from routes.maintenance import manejar_eliminacion_proveedor  # noqa: E402


def test_mantenimiento_eliminacion_delega_al_handler(monkeypatch):
    flujo = {"state": "awaiting_deletion_confirmation"}
    llamadas = []

    async def _fake_confirmar_eliminacion(**kwargs):
        llamadas.append(kwargs)
        return {
            "success": True,
            "messages": [{"response": "ok"}],
            "persist_flow": False,
        }

    monkeypatch.setattr(
        modulo_deletion,
        "manejar_confirmacion_eliminacion",
        _fake_confirmar_eliminacion,
    )

    resultado = asyncio.run(
        manejar_eliminacion_proveedor(
            flujo=flujo,
            texto_mensaje="si",
            supabase=None,
            telefono="593999111299@s.whatsapp.net",
        )
    )

    assert resultado["success"] is True
    assert resultado["persist_flow"] is False
    assert resultado["messages"][0]["response"] == "ok"
    assert llamadas[0]["flujo"] is flujo
