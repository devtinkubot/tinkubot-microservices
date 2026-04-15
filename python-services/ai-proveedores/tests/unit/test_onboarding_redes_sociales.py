import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.onboarding.handlers.redes_sociales as modulo_redes  # noqa: E402
from templates.onboarding.redes_sociales import REDES_SOCIALES_SKIP_ID  # noqa: E402


def test_onboarding_redes_sociales_publica_evento_con_phone_recuperado(monkeypatch):
    captured = {}

    async def _fake_publicar_evento_onboarding(*, event_type, flujo, payload, **_):
        captured["event_type"] = event_type
        captured["phone"] = flujo.get("phone")
        captured["payload"] = payload
        return "stream-1"

    monkeypatch.setattr(
        modulo_redes,
        "onboarding_async_persistence_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        modulo_redes,
        "publicar_evento_onboarding",
        _fake_publicar_evento_onboarding,
    )

    flujo = {
        "state": "onboarding_social_media",
        "provider_id": "prov-1",
        "from_number": "593999111299@s.whatsapp.net",
    }

    respuesta = asyncio.run(
        modulo_redes.manejar_espera_red_social_onboarding(
            flujo=flujo,
            texto_mensaje="Facebook diego.unkuch",
            selected_option=None,
            supabase=None,
        )
    )

    assert respuesta["messages"]
    assert flujo["state"] == "review_pending_verification"
    assert captured["event_type"] == modulo_redes.EVENT_TYPE_SOCIAL
    assert captured["phone"] == "593999111299@s.whatsapp.net"
    assert captured["payload"]["checkpoint"] == "review_pending_verification"
    assert captured["payload"]["facebook_username"] == "diego.unkuch"
    assert "social_media_url" not in captured["payload"]
    assert "social_media_type" not in captured["payload"]


def test_onboarding_redes_sociales_skip_publica_evento_con_phone_recuperado(
    monkeypatch,
):
    captured = {}

    async def _fake_publicar_evento_onboarding(*, event_type, flujo, payload, **_):
        captured["event_type"] = event_type
        captured["phone"] = flujo.get("phone")
        captured["payload"] = payload
        return "stream-2"

    monkeypatch.setattr(
        modulo_redes,
        "onboarding_async_persistence_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        modulo_redes,
        "publicar_evento_onboarding",
        _fake_publicar_evento_onboarding,
    )

    flujo = {
        "state": "onboarding_social_media",
        "provider_id": "prov-2",
        "from_number": "593999111288@s.whatsapp.net",
    }

    respuesta = asyncio.run(
        modulo_redes.manejar_espera_red_social_onboarding(
            flujo=flujo,
            texto_mensaje=None,
            selected_option=REDES_SOCIALES_SKIP_ID,
            supabase=None,
        )
    )

    assert respuesta["messages"]
    assert flujo["state"] == "review_pending_verification"
    assert captured["event_type"] == modulo_redes.EVENT_TYPE_SOCIAL
    assert captured["phone"] == "593999111288@s.whatsapp.net"
    assert captured["payload"]["checkpoint"] == "review_pending_verification"
    assert captured["payload"]["facebook_username"] is None
    assert captured["payload"]["instagram_username"] is None
    assert "social_media_url" not in captured["payload"]
    assert "social_media_type" not in captured["payload"]
