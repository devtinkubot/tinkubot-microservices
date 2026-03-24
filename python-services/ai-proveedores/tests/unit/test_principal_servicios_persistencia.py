import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import principal  # noqa: E402


def test_sincronizar_servicios_si_cambiaron_persiste_cambios(monkeypatch):
    llamadas = []

    async def _fake_actualizar_servicios(proveedor_id, servicios):
        llamadas.append((proveedor_id, list(servicios)))
        return ["Plomeria", "Electricidad"]

    monkeypatch.setattr(principal, "supabase", object())
    monkeypatch.setattr(principal, "actualizar_servicios", _fake_actualizar_servicios)

    flujo_anterior = {"provider_id": "prov-1", "services": ["Plomeria"]}
    flujo_actual = {
        "provider_id": "prov-1",
        "servicios_temporales": ["Plomeria", "Electricidad"],
    }

    resultado = asyncio.run(
        principal._sincronizar_servicios_si_cambiaron(
            flujo_anterior,
            flujo_actual,
        )
    )

    assert resultado is True
    assert llamadas == [("prov-1", ["Plomeria", "Electricidad"])]
    assert flujo_actual["services"] == ["Plomeria", "Electricidad"]
    assert flujo_actual["servicios_temporales"] == ["Plomeria", "Electricidad"]


def test_sincronizar_servicios_si_cambiaron_ignora_listas_iguales(monkeypatch):
    llamadas = []

    async def _fake_actualizar_servicios(proveedor_id, servicios):
        llamadas.append((proveedor_id, list(servicios)))
        return list(servicios)

    monkeypatch.setattr(principal, "supabase", object())
    monkeypatch.setattr(principal, "actualizar_servicios", _fake_actualizar_servicios)

    flujo_anterior = {"provider_id": "prov-1", "services": ["Plomeria"]}
    flujo_actual = {"provider_id": "prov-1", "services": ["Plomeria"]}

    resultado = asyncio.run(
        principal._sincronizar_servicios_si_cambiaron(
            flujo_anterior,
            flujo_actual,
        )
    )

    assert resultado is False
    assert llamadas == []
