from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.onboarding.worker import ejecutar_limpieza_onboarding  # noqa: E402


@pytest.mark.asyncio
async def test_ejecutar_limpieza_onboarding_delega_en_limpieza(monkeypatch):
    captured = {}

    async def _fake_limpieza(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"deleted": 1}

    monkeypatch.setattr(
        "services.onboarding.worker.limpiar_onboarding_proveedores",
        _fake_limpieza,
    )

    resultado = await ejecutar_limpieza_onboarding(
        supabase=object(),
        whatsapp_url="http://wa-gateway:7000",
        whatsapp_account_id="bot-proveedores",
        warning_hours=48,
        expiry_hours=72,
    )

    assert resultado["success"] is True
    assert resultado["result"] == {"deleted": 1}
    assert captured["args"][1] == "http://wa-gateway:7000"
    assert captured["args"][2] == "bot-proveedores"


@pytest.mark.asyncio
async def test_ejecutar_limpieza_onboarding_sin_supabase_falla():
    resultado = await ejecutar_limpieza_onboarding(
        supabase=None,
        whatsapp_url="http://wa-gateway:7000",
        whatsapp_account_id="bot-proveedores",
        warning_hours=48,
        expiry_hours=72,
    )

    assert resultado["success"] is False
