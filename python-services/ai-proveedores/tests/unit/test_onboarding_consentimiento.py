from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.onboarding.consentimiento import (  # noqa: E402
    procesar_respuesta_consentimiento_onboarding,
)


@pytest.mark.asyncio
async def test_consentimiento_onboarding_aceptado_actualiza_flujo_y_registra(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "awaiting_consent",
        "id": "prov-123",
        "full_name": "Proveedor Demo",
        "has_consent": False,
    }

    async def _fake_establecer_flujo(_telefono: str, flujo_guardado: Dict[str, Any]):
        captured["flow"] = dict(flujo_guardado)

    async def _fake_run_supabase(*_args, **_kwargs):
        return None

    async def _fake_registrar_consentimiento(
        proveedor_id: str | None,
        telefono: str,
        carga: Dict[str, Any],
        respuesta: str,
    ):
        captured["registro"] = {
            "proveedor_id": proveedor_id,
            "telefono": telefono,
            "respuesta": respuesta,
            "message": carga.get("message"),
        }

    monkeypatch.setattr(
        "services.onboarding.consentimiento.establecer_flujo",
        _fake_establecer_flujo,
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )

    respuesta = await procesar_respuesta_consentimiento_onboarding(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        carga={
            "selected_option": "1",
            "message": "Acepto",
            "content": "Acepto",
            "timestamp": "2026-03-23T00:00:00Z",
        },
        perfil_proveedor={"id": "prov-123", "full_name": "Proveedor Demo"},
    )

    assert captured["flow"]["state"] == "pending_verification"
    assert captured["flow"]["has_consent"] is True
    assert captured["registro"]["respuesta"] == "accepted"
    assert "revis" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_consentimiento_onboarding_rechazado_reinicia_flujo(monkeypatch):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "awaiting_consent",
        "id": "prov-123",
        "has_consent": False,
    }

    async def _fake_reiniciar_flujo(_telefono: str):
        captured["reinicio"] = True

    async def _fake_run_supabase(*_args, **_kwargs):
        return None

    async def _fake_registrar_consentimiento(*_args, **_kwargs):
        captured["registro"] = True

    monkeypatch.setattr(
        "services.onboarding.consentimiento.reiniciar_flujo",
        _fake_reiniciar_flujo,
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )

    respuesta = await procesar_respuesta_consentimiento_onboarding(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        carga={"selected_option": "2", "message": "No", "content": "No"},
        perfil_proveedor={"id": "prov-123"},
    )

    assert captured["reinicio"] is True
    assert captured["registro"] is True
    assert "entendido" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_consentimiento_onboarding_no_acepta_texto_largo_que_empieza_con_uno(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    called = {"registro": False}
    flujo = {
        "state": "awaiting_consent",
        "id": "prov-123",
        "has_consent": False,
    }

    async def _fake_registrar_consentimiento(*_args, **_kwargs):
        called["registro"] = True

    monkeypatch.setattr(
        "services.onboarding.consentimiento.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )

    respuesta = await procesar_respuesta_consentimiento_onboarding(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        carga={
            "message": "1 desarrollo de software empresarial con IA",
            "content": "1 desarrollo de software empresarial con IA",
        },
        perfil_proveedor={"id": "prov-123"},
    )

    assert called["registro"] is False
    assert flujo["state"] == "awaiting_consent"
    assert "política de privacidad" in respuesta["messages"][0]["response"].lower()
    assert "aceptar" in respuesta["messages"][0]["response"].lower()
