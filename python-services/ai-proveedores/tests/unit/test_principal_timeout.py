import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None  # type: ignore[attr-defined]
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.router as modulo_router  # noqa: E402


def test_sesion_no_expira_con_inactividad_menor_al_umbral():
    ahora = datetime.now(timezone.utc)
    flujo = {
        "last_seen_at": (ahora - timedelta(minutes=10)).isoformat(),
    }

    assert modulo_router._sesion_expirada_por_inactividad(flujo, ahora) is False


def test_sesion_expira_cuando_supera_el_umbral():
    ahora = datetime.now(timezone.utc)
    flujo = {
        "last_seen_at": (ahora - timedelta(hours=2)).isoformat(),
    }

    assert modulo_router._sesion_expirada_por_inactividad(flujo, ahora) is True


def test_reanudacion_onboarding_ciudad_repite_mismo_paso():
    flujo = {"state": "onboarding_city"}

    resultado = modulo_router._construir_reanudacion_onboarding(flujo)

    assert resultado["messages"][0]["response"].startswith("⌛ He detectado")
    assert resultado["messages"][1]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


def test_reanudacion_onboarding_dni_repite_cedula():
    flujo = {"state": "onboarding_dni_front_photo"}

    resultado = modulo_router._construir_reanudacion_onboarding(flujo)

    assert resultado["messages"][1]["response"].startswith(
        "*Envía una foto frontal de tu cédula.*"
    )


def test_reanudacion_awaiting_menu_option_registrado_muestra_menu_operativo():
    flujo = {"state": "awaiting_menu_option"}

    resultado = modulo_router._construir_reanudacion_onboarding(
        flujo,
        esta_registrado=True,
    )

    assert resultado["messages"][1]["ui"]["type"] == "list"
    assert resultado["messages"][1]["ui"]["id"] == "provider_main_menu_v1"
    assert "Aceptar" not in resultado["messages"][1]["response"]


def test_manejar_mensaje_reanudacion_menu_registrado_no_falla(monkeypatch):
    flujo = {
        "state": "awaiting_menu_option",
        "last_seen_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "provider_id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
        "has_consent": True,
    }

    monkeypatch.setattr(
        modulo_router,
        "_sesion_expirada_por_inactividad",
        lambda *_args, **_kwargs: True,
    )

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593959091325@s.whatsapp.net",
            texto_mensaje="Hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor={
                "id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
                "has_consent": True,
                "status": "approved",
                "onboarding_complete": True,
            },
            supabase=None,
            servicio_embeddings=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None
            ),
        )
    )

    assert resultado["response"]["messages"][1]["ui"]["id"] == "provider_main_menu_v1"


def test_manejar_mensaje_aprobado_incompleto_no_reanuda_menu_operativo(monkeypatch):
    flujo = {
        "state": "awaiting_menu_option",
        "last_seen_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "provider_id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
        "has_consent": True,
    }

    monkeypatch.setattr(
        modulo_router,
        "_sesion_expirada_por_inactividad",
        lambda *_args, **_kwargs: True,
    )

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593959091326@s.whatsapp.net",
            texto_mensaje="Hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor={
                "id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
                "has_consent": True,
                "status": "approved",
                "onboarding_complete": False,
                "city": "Quito",
                "dni_front_photo_url": "dni-front.jpg",
                "face_photo_url": "face.jpg",
                "experience_range": "",
                "services_list": [],
            },
            supabase=None,
            servicio_embeddings=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None
            ),
        )
    )

    assert flujo["state"] == "onboarding_experience"
    assert "años de experiencia" in resultado["response"]["messages"][1]["response"].lower()


def test_manejar_mensaje_no_descarta_ubicacion_tardia(monkeypatch):
    flujo = {
        "state": "onboarding_city",
        "last_seen_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "provider_id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
        "has_consent": True,
    }
    enrutar_llamadas = []

    monkeypatch.setattr(
        modulo_router,
        "_sesion_expirada_por_inactividad",
        lambda *_args, **_kwargs: True,
    )

    async def _fallar_timeout(*_args, **_kwargs):
        raise AssertionError("No debe entrar al timeout para mensajes accionables")

    async def _fake_enrutar_estado(**kwargs):
        enrutar_llamadas.append(kwargs)
        return {
            "response": {"success": True, "messages": [{"response": "ok"}]},
            "persist_flow": True,
            "new_flow": kwargs["flujo"],
        }

    monkeypatch.setattr(
        modulo_router,
        "_manejar_timeout_inactividad",
        _fallar_timeout,
    )
    monkeypatch.setattr(modulo_router, "enrutar_estado", _fake_enrutar_estado)

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593959091325@s.whatsapp.net",
            texto_mensaje="",
            carga={"location": {"latitude": -2.9039, "longitude": -78.9838}},
            opcion_menu=None,
            perfil_proveedor={
                "id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
                "has_consent": True,
            },
            supabase=None,
            servicio_embeddings=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None
            ),
        )
    )

    assert resultado["response"]["messages"][0]["response"] == "ok"
    assert enrutar_llamadas


def test_manejar_mensaje_en_revision_no_reanuda_onboarding(monkeypatch):
    flujo = {
        "state": "onboarding_add_another_service",
        "last_seen_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "provider_id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
        "has_consent": True,
    }

    monkeypatch.setattr(
        modulo_router,
        "_sesion_expirada_por_inactividad",
        lambda *_args, **_kwargs: True,
    )

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593959091325@s.whatsapp.net",
            texto_mensaje="Hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor={
                "id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11",
                "has_consent": True,
                "status": "pending",
                "city": "Quito",
                "dni_front_photo_url": "dni-front.jpg",
                "face_photo_url": "face.jpg",
                "experience_range": "3 a 5 años",
                "services_list": ["Plomería"],
                "document_first_names": "Ana",
                "document_last_names": "Pérez",
            },
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None
            ),
        )
    )

    assert resultado is not None
    respuestas = [
        mensaje.get("response", "").lower()
        for mensaje in resultado["response"]["messages"]
    ]
    assert any("revis" in respuesta for respuesta in respuestas)
    assert all("retomamos el último paso" not in respuesta for respuesta in respuestas)
