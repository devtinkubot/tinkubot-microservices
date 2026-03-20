import sys
import types
from pathlib import Path

import pytest

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from principal import (  # noqa: E402
    _es_mensaje_interactivo_duplicado,
    _es_mensaje_multimedia_duplicado,
)


class _RedisStub:
    def __init__(self):
        self.keys = set()

    async def set_if_absent(self, key, value, expire=None):
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


@pytest.mark.asyncio
async def test_dedupe_multimedia_ignora_reentrega_con_mismo_message_id(monkeypatch):
    redis_stub = _RedisStub()
    monkeypatch.setattr("principal.cliente_redis", redis_stub)

    carga = {"id": "wamid-1", "image_base64": "abc123"}

    primera = await _es_mensaje_multimedia_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_dni_front_photo",
        carga,
    )
    segunda = await _es_mensaje_multimedia_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_dni_front_photo",
        carga,
    )

    assert primera is False
    assert segunda is True


@pytest.mark.asyncio
async def test_dedupe_interactivo_ignora_reentrega_con_mismo_message_id(monkeypatch):
    redis_stub = _RedisStub()
    monkeypatch.setattr("principal.cliente_redis", redis_stub)

    carga = {
        "id": "wamid-interactive-1",
        "message_type": "interactive_button_reply",
        "selected_option": "continue_provider_onboarding",
    }

    primera = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_consent",
        carga,
    )
    segunda = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_consent",
        carga,
    )

    assert primera is False
    assert segunda is True


@pytest.mark.asyncio
async def test_dedupe_interactivo_accion_unica(monkeypatch):
    redis_stub = _RedisStub()
    monkeypatch.setattr("principal.cliente_redis", redis_stub)

    primera = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_certificate",
        {
            "id": "wamid-interactive-10",
            "message_type": "interactive_button_reply",
            "selected_option": "skip_profile_certificate",
        },
    )
    segunda = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_specialty",
        {
            "id": "wamid-interactive-11",
            "message_type": "interactive_button_reply",
            "selected_option": "skip_profile_certificate",
        },
    )

    assert primera is False
    assert segunda is False


@pytest.mark.asyncio
async def test_dedupe_interactivo_confirmacion_servicio_sin_message_id(
    monkeypatch,
):
    redis_stub = _RedisStub()
    monkeypatch.setattr("principal.cliente_redis", redis_stub)

    carga = {
        "message_type": "interactive_button_reply",
        "selected_option": "profile_service_confirm",
    }

    primera = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_service_add_confirmation",
        carga,
        flujo={"services": ["uno", "dos"]},
    )
    segunda = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_service_action",
        carga,
        flujo={"services": ["uno", "dos", "tres"]},
    )

    assert primera is False
    assert segunda is False


@pytest.mark.asyncio
async def test_dedupe_interactivo_confirmacion_servicio_con_nonce_diferente(
    monkeypatch,
):
    redis_stub = _RedisStub()
    monkeypatch.setattr("principal.cliente_redis", redis_stub)

    carga = {
        "message_type": "interactive_button_reply",
        "selected_option": "profile_service_confirm",
    }

    primera = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_service_add_confirmation",
        carga,
        flujo={
            "services": ["uno", "dos"],
            "service_add_confirmation_nonce": "nonce-a",
        },
    )
    segunda = await _es_mensaje_interactivo_duplicado(
        "593999111222@s.whatsapp.net",
        "awaiting_service_add_confirmation",
        carga,
        flujo={
            "services": ["uno", "dos"],
            "service_add_confirmation_nonce": "nonce-b",
        },
    )

    assert primera is False
    assert segunda is False
