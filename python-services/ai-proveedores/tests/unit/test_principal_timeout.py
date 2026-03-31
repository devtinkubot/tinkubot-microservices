import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncio

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.router as modulo_router  # noqa: E402


def test_sesion_no_expira_con_inactividad_menor_al_umbral():
    ahora = datetime.now(timezone.utc)
    flujo = {
        "last_seen_at": (ahora - timedelta(minutes=10)).isoformat(),
    }

    assert (
        modulo_router._sesion_expirada_por_inactividad(flujo, ahora) is False
    )


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

    monkeypatch.setattr(modulo_router, "_sesion_expirada_por_inactividad", lambda *_args, **_kwargs: True)

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593959091325@s.whatsapp.net",
            texto_mensaje="Hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor={"id": "c4f1f0f2-4a6d-4e8d-9c0a-2d2c7f4d5a11", "has_consent": True},
            supabase=None,
            servicio_embeddings=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None),
        )
    )

    assert resultado["response"]["messages"][1]["ui"]["id"] == "provider_main_menu_v1"
