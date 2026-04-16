from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

imghdr_stub: Any = types.ModuleType("imghdr")
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
        "state": "onboarding_consent",
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
        "services.onboarding.session.establecer_flujo", _fake_establecer_flujo
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase", _fake_run_supabase
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

    assert captured["flow"]["state"] == "onboarding_city"
    assert captured["flow"]["has_consent"] is True
    assert captured["flow"]["real_phone"] == "593999111222"
    assert captured["flow"].get("requires_real_phone") is False
    assert captured["registro"]["respuesta"] == "accepted"
    assert respuesta["messages"][0]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


@pytest.mark.asyncio
async def test_consentimiento_onboarding_aceptado_crea_borrador_si_no_hay_provider_id(
    monkeypatch,
):
    monkeypatch.setattr("dependencies.deps.supabase", object())

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "onboarding_consent",
        "has_consent": False,
    }

    async def _fake_asegurar_proveedor_borrador(_supabase, telefono: str):
        captured["draft_phone"] = telefono
        return {"id": "prov-draft-1", "phone": telefono}

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
        }

    monkeypatch.setattr(
        "services.onboarding.consentimiento.asegurar_proveedor_borrador",
        _fake_asegurar_proveedor_borrador,
    )
    monkeypatch.setattr(
        "services.onboarding.session.establecer_flujo", _fake_establecer_flujo
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase", _fake_run_supabase
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
        perfil_proveedor=None,
    )

    assert captured["draft_phone"] == "593999111222@s.whatsapp.net"
    assert captured["flow"]["state"] == "onboarding_city"
    assert captured["flow"]["provider_id"] == "prov-draft-1"
    assert captured["registro"]["proveedor_id"] == "prov-draft-1"
    assert respuesta["messages"][0]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


@pytest.mark.asyncio
async def test_consentimiento_onboarding_persiste_metadata_whatsapp_al_aceptar(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "onboarding_consent",
        "display_name": "@DiegoUnkuch",
        "formatted_name": "",
        "first_name": "",
        "last_name": "",
        "has_consent": False,
    }

    class _Query:
        def update(self, payload):
            captured["payload"] = dict(payload)
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return None

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "providers"
            return _Query()

    async def _fake_establecer_flujo(_telefono: str, flujo_guardado: Dict[str, Any]):
        captured["flow"] = dict(flujo_guardado)

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

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
        }

    monkeypatch.setattr(
        "services.onboarding.session.establecer_flujo", _fake_establecer_flujo
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase", _fake_run_supabase
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
        },
        perfil_proveedor={"id": "prov-123", "full_name": "Proveedor Demo"},
        supabase=_SupabaseStub(),
    )

    assert captured["payload"]["has_consent"] is True
    assert captured["payload"]["display_name"] == "@DiegoUnkuch"
    assert "formatted_name" not in captured["payload"]
    assert "first_name" not in captured["payload"]
    assert "last_name" not in captured["payload"]
    assert captured["payload"]["real_phone"] == "593999111222"
    assert captured["registro"]["respuesta"] == "accepted"
    assert respuesta["messages"][0]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


@pytest.mark.asyncio
async def test_consentimiento_onboarding_sin_jid_numerico_pide_real_phone(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "onboarding_consent",
        "id": "prov-123",
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
        }

    monkeypatch.setattr(
        "services.onboarding.session.establecer_flujo", _fake_establecer_flujo
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase", _fake_run_supabase
    )
    monkeypatch.setattr(
        "services.onboarding.consentimiento.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )

    respuesta = await procesar_respuesta_consentimiento_onboarding(
        telefono="106214625132641@lid",
        flujo=flujo,
        carga={
            "selected_option": "1",
            "message": "Acepto",
            "content": "Acepto",
        },
        perfil_proveedor={"id": "prov-123", "full_name": "Proveedor Demo"},
    )

    assert captured["flow"]["state"] == "onboarding_real_phone"
    assert captured["flow"]["requires_real_phone"] is True
    assert "real_phone" not in captured["flow"]
    assert respuesta["messages"][0].lower().startswith(
        "*para continuar, escribe tu número de celular"
    )


@pytest.mark.asyncio
async def test_consentimiento_onboarding_rechazo_inesperado_reemite_solicitud(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "onboarding_consent",
        "id": "prov-123",
        "has_consent": False,
    }

    async def _fake_run_supabase(*_args, **_kwargs):
        return None

    async def _fake_registrar_consentimiento(*_args, **_kwargs):
        captured["registro"] = True

    monkeypatch.setattr(
        "services.onboarding.consentimiento.run_supabase", _fake_run_supabase
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

    assert "registro" not in captured
    assert flujo["state"] == "onboarding_consent"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Aceptar"
    assert "política de privacidad" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_consentimiento_onboarding_no_acepta_texto_largo_que_empieza_con_uno(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    called = {"registro": False}
    flujo = {
        "state": "onboarding_consent",
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
    assert flujo["state"] == "onboarding_consent"
    assert "política de privacidad" in respuesta["messages"][0]["response"].lower()
    assert "aceptar" in respuesta["messages"][0]["response"].lower()
