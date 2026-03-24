import asyncio
import sys
import types
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.router as modulo_router  # noqa: E402
import flows.onboarding.router as modulo_onboarding_router  # noqa: E402
from flows.router import enrutar_estado, manejar_mensaje
from templates.onboarding.inicio import ONBOARDING_REGISTER_BUTTON_ID


def _ejecutar_enrutado(flujo, texto_mensaje, opcion_menu=None):
    return asyncio.run(
        enrutar_estado(
            estado=flujo.get("state"),
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            carga={},
            telefono="593999111299@s.whatsapp.net",
            opcion_menu=opcion_menu,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )


def test_estado_esperando_disponibilidad_mantiene_flujo():
    flujo = {"state": "awaiting_availability_response"}
    resultado = _ejecutar_enrutado(flujo, "hola")

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_availability_response"
    assert "solicitud pendiente de disponibilidad" in resultado["response"]["messages"][0][
        "response"
    ].lower()
    assert "disponible" in resultado["response"]["messages"][0]["response"].lower()
    assert "no disponible" in resultado["response"]["messages"][0]["response"].lower()


def test_estado_esperando_disponibilidad_permite_volver_menu():
    flujo = {"state": "awaiting_availability_response"}
    resultado = _ejecutar_enrutado(flujo, "menu")

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_menu_option"
    assert resultado["response"]["messages"]


def test_reset_solo_devuelve_mensaje_de_reinicio():
    flujo = {"state": "awaiting_city"}
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)
    modulo_router.reiniciar_flujo = lambda _telefono: asyncio.sleep(0)
    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="reiniciar",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert flujo["state"] is None
    assert resultado["persist_flow"] is False
    assert len(resultado["response"]["messages"]) == 1
    assert "reinici" in resultado["response"]["messages"][0]["response"].lower()


def test_boton_onboarding_registrarse_abre_ciudad(monkeypatch):
    flujo = {"state": "awaiting_menu_option", "mode": "registration"}

    async def _fake_asegurar_proveedor_borrador(*args, **kwargs):
        return {"id": "prov-draft-1"}

    monkeypatch.setattr(
        modulo_onboarding_router,
        "asegurar_proveedor_borrador",
        _fake_asegurar_proveedor_borrador,
    )

    resultado = asyncio.run(
        enrutar_estado(
            estado=flujo.get("state"),
            flujo=flujo,
            texto_mensaje="onboarding_register_button",
            carga={"selected_option": ONBOARDING_REGISTER_BUTTON_ID},
            telefono="593999111299@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=False,
            esta_registrado=False,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_city"
    assert resultado["response"]["response"].startswith("Ahora comparte tu *ubicación*")
    assert resultado["response"]["ui"]["type"] == "location_request"


def test_redes_sociales_onboarding_nuevo_y_legacy_separados():
    assert modulo_onboarding_router.es_estado_onboarding("awaiting_social_media") is False
    assert (
        modulo_onboarding_router.es_estado_onboarding(
            "awaiting_social_media_onboarding"
        )
        is True
    )
    assert (
        modulo_onboarding_router.es_estado_onboarding(
            "awaiting_onboarding_social_facebook_username"
        )
        is False
    )
    assert (
        modulo_onboarding_router.es_estado_onboarding(
            "awaiting_onboarding_social_instagram_username"
        )
        is False
    )


def test_numero_sin_provider_id_no_pasa_por_clasificacion_legacy(monkeypatch):
    flujo = {}
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)

    async def _fake_manejar_entrada_onboarding(**kwargs):
        assert kwargs["flujo"].get("state") is None
        return {
            "success": True,
            "messages": [
                {
                    "response": "¡Hola! Vamos a crear tu perfil de proveedor paso a paso."
                }
            ],
        }

    def _legacy_no_deberia_llamarse(*_args, **_kwargs):
        raise AssertionError("La clasificación legacy no debe ejecutarse sin provider_id")

    monkeypatch.setattr(
        modulo_router,
        "manejar_entrada_onboarding",
        _fake_manejar_entrada_onboarding,
    )
    monkeypatch.setattr(modulo_router, "resolver_estado_registro", _legacy_no_deberia_llamarse)

    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="Hola, quiero registrarme",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert resultado["response"]["messages"][0]["response"].startswith(
        "¡Hola! Vamos a crear tu perfil de proveedor"
    )


def test_boton_onboarding_no_repite_bienvenida(monkeypatch):
    flujo = {"state": "awaiting_menu_option", "mode": "registration"}
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)

    async def _fake_asegurar_proveedor_borrador(*args, **kwargs):
        return {"id": "prov-draft-1"}

    monkeypatch.setattr(
        modulo_onboarding_router,
        "asegurar_proveedor_borrador",
        _fake_asegurar_proveedor_borrador,
    )

    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="onboarding_register_button",
            carga={"selected_option": ONBOARDING_REGISTER_BUTTON_ID},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_city"
    assert flujo["provider_id"] == "prov-draft-1"
    assert resultado["response"]["messages"][0]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


def test_inactividad_menor_al_umbral_no_reinicia(monkeypatch):
    ahora = datetime.now(timezone.utc)
    flujo = {
        "state": "awaiting_city",
        "last_seen_at": (ahora - timedelta(minutes=10)).isoformat(),
    }
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)
    reinicios = []

    async def _fake_reiniciar_flujo(_telefono):
        reinicios.append(_telefono)

    async def _fake_enrutar_estado(**_kwargs):
        return {
            "response": {
                "success": True,
                "messages": [{"response": "continuar"}],
            },
            "persist_flow": True,
        }

    monkeypatch.setattr(modulo_router, "reiniciar_flujo", _fake_reiniciar_flujo)
    monkeypatch.setattr(modulo_router, "enrutar_estado", _fake_enrutar_estado)

    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert reinicios == []
    assert resultado["response"]["messages"][0]["response"] == "continuar"


def test_inactividad_mayor_al_umbral_reinicia(monkeypatch):
    ahora = datetime.now(timezone.utc)
    flujo = {
        "state": "awaiting_city",
        "last_seen_at": (ahora - timedelta(hours=2)).isoformat(),
    }
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)
    reinicios = []

    async def _fake_reiniciar_flujo(_telefono):
        reinicios.append(_telefono)

    def _legacy_no_deberia_llamarse(*_args, **_kwargs):
        raise AssertionError("No debe continuar al enrutado normal si expiró")

    monkeypatch.setattr(modulo_router, "reiniciar_flujo", _fake_reiniciar_flujo)
    monkeypatch.setattr(modulo_router, "enrutar_estado", _legacy_no_deberia_llamarse)
    monkeypatch.setattr(
        modulo_router,
        "resolver_estado_registro",
        lambda *_args, **_kwargs: (False, False, False, False),
    )
    monkeypatch.setattr(
        modulo_router,
        "sincronizar_flujo_con_perfil",
        lambda flujo, _perfil: flujo,
    )
    monkeypatch.setattr(
        modulo_router,
        "construir_payload_menu_principal",
        lambda **_kwargs: {"response": "menu"},
    )
    monkeypatch.setattr(
        modulo_router,
        "manejar_pendiente_revision",
        lambda *_args, **_kwargs: None,
    )

    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert reinicios == ["593999111299@s.whatsapp.net"]
