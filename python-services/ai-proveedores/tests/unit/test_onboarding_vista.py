from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.onboarding.vista import obtener_vista_onboarding  # noqa: E402


@pytest.mark.asyncio
async def test_vista_onboarding_reconstruye_estado_desde_supabase(monkeypatch):
    async def _fake_obtener_perfil(_telefono: str):
        return {
            "id": "prov-1",
            "status": "approved_basic",
            "has_consent": True,
            "full_name": "Proveedor Demo",
            "city": "Quito",
            "dni_front_photo_url": "dni-front",
            "face_photo_url": "face-photo",
            "experience_range": "1-3",
            "services_list": ["cerrajería"],
        }

    monkeypatch.setattr(
        "services.onboarding.vista.obtener_perfil_proveedor_cacheado",
        _fake_obtener_perfil,
    )

    vista = await obtener_vista_onboarding(
        telefono="593999111222@s.whatsapp.net",
        flujo={},
        perfil_proveedor=None,
    )

    assert vista["flujo"]["state"] == "awaiting_menu_option"
    assert vista["checkpoint"] == "awaiting_menu_option"
    assert vista["esta_registrado"] is True
    assert vista["tiene_consentimiento"] is True
    assert vista["es_perfil_completo"] is True


@pytest.mark.asyncio
async def test_vista_onboarding_respeta_flujo_proporcionado(monkeypatch):
    async def _fake_obtener_perfil(_telefono: str):
        return {
            "id": "prov-1",
            "status": "pending",
            "has_consent": False,
            "full_name": "Proveedor Demo",
        }

    monkeypatch.setattr(
        "services.onboarding.vista.obtener_perfil_proveedor_cacheado",
        _fake_obtener_perfil,
    )

    vista = await obtener_vista_onboarding(
        telefono="593999111222@s.whatsapp.net",
        flujo={"state": "onboarding_city", "provider_id": "prov-1"},
        perfil_proveedor=None,
    )

    assert vista["estado"] == "onboarding_city"
    assert vista["flujo"]["provider_id"] == "prov-1"
    assert vista["tiene_consentimiento"] is False
