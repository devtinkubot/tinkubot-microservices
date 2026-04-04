import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.mensajes import RecepcionMensajeWhatsApp  # noqa: E402
import services.shared.orquestacion_whatsapp as modulo_orquestacion  # noqa: E402


def test_procesar_mensaje_whatsapp_difiere_servicios_async_y_no_sincroniza(
    monkeypatch,
):
    capturado = {}

    async def _fake_obtener_flujo(_telefono):
        return {
            "provider_id": "prov-1",
            "state": "onboarding_specialty",
            "services": ["Plomeria"],
            "servicios_detallados": [
                {
                    "raw_service_text": "Plomeria",
                    "service_name": "Plomeria",
                }
            ],
        }

    async def _fake_obtener_perfil_proveedor_cacheado(*_args, **_kwargs):
        return {"id": "prov-1", "has_consent": True}

    async def _fake_obtener_vista_onboarding(**kwargs):
        return {
            "flujo": kwargs["flujo"],
            "perfil_proveedor": kwargs["perfil_proveedor"],
        }

    async def _fake_manejar_mensaje(**kwargs):
        flujo = kwargs["flujo"]
        flujo["state"] = "onboarding_add_another_service"
        flujo["services"] = ["Plomeria", "Electricidad"]
        flujo["servicios_temporales"] = ["Plomeria", "Electricidad"]
        flujo["servicios_detallados"] = [
            {
                "raw_service_text": "Plomeria",
                "service_name": "Plomeria",
            },
            {
                "raw_service_text": "Electricidad",
                "service_name": "Electricidad",
            },
        ]
        return {
            "response": {"success": True, "messages": [{"response": "ok"}]},
            "new_flow": flujo,
            "persist_flow": True,
        }

    async def _fake_publicar_evento_onboarding(**kwargs):
        capturado.update(kwargs)
        return "stream-1"

    async def _fake_establecer_flujo(*_args, **_kwargs):
        return None

    async def _fake_false(*_args, **_kwargs):
        return False

    async def _fake_alias(telefono):
        return telefono

    async def _fake_noop_response(*_args, **_kwargs):
        return None

    async def _fake_false_duplicate(*_args, **_kwargs):
        return False

    async def _fake_no_usar(*_args, **_kwargs):
        raise AssertionError("No debe llamarse a la sincronización pesada")

    monkeypatch.setattr(modulo_orquestacion, "obtener_flujo", _fake_obtener_flujo)
    monkeypatch.setattr(
        modulo_orquestacion,
        "obtener_perfil_proveedor_cacheado",
        _fake_obtener_perfil_proveedor_cacheado,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "obtener_vista_onboarding",
        _fake_obtener_vista_onboarding,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "manejar_mensaje",
        _fake_manejar_mensaje,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "sincronizar_servicios_si_cambiaron",
        _fake_no_usar,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "publicar_evento_onboarding",
        _fake_publicar_evento_onboarding,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "onboarding_async_persistence_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "establecer_flujo",
        _fake_establecer_flujo,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_hay_contexto_disponibilidad_activo",
        _fake_false,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_resolver_alias_disponibilidad",
        _fake_alias,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_registrar_respuesta_disponibilidad_si_aplica",
        _fake_noop_response,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "es_mensaje_multimedia_duplicado",
        _fake_false_duplicate,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "es_mensaje_interactivo_duplicado",
        _fake_false_duplicate,
    )

    solicitud = RecepcionMensajeWhatsApp(
        id="msg-1",
        phone="593959091325@s.whatsapp.net",
        from_number="593959091325@s.whatsapp.net",
        message="Servicios de jardinería y poda de árboles",
    )

    respuesta = asyncio.run(
        modulo_orquestacion.procesar_mensaje_whatsapp(
            solicitud=solicitud,
            supabase=object(),
            servicio_embeddings=None,
            cliente_openai=None,
            logger=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None),
        )
    )

    assert respuesta["messages"][0]["response"] == "ok"
    assert capturado["event_type"] == modulo_orquestacion.EVENT_TYPE_SERVICES
    assert capturado["source_message_id"] == "msg-1"
    assert capturado["payload"]["checkpoint"] == "onboarding_add_another_service"
    assert capturado["payload"]["services"] == ["Plomeria", "Electricidad"]
    assert capturado["payload"]["raw_service_text"] == "Electricidad"
    assert capturado["payload"]["service_position"] == 1


def test_procesar_mensaje_whatsapp_recurre_a_sincronizacion_si_no_publica_evento(
    monkeypatch,
):
    llamadas_sync = []

    async def _fake_obtener_flujo(_telefono):
        return {
            "provider_id": "prov-1",
            "state": "onboarding_specialty",
            "services": ["Plomeria"],
            "servicios_detallados": [
                {
                    "raw_service_text": "Plomeria",
                    "service_name": "Plomeria",
                }
            ],
        }

    async def _fake_obtener_perfil_proveedor_cacheado(*_args, **_kwargs):
        return {"id": "prov-1", "has_consent": True}

    async def _fake_obtener_vista_onboarding(**kwargs):
        return {
            "flujo": kwargs["flujo"],
            "perfil_proveedor": kwargs["perfil_proveedor"],
        }

    async def _fake_manejar_mensaje(**kwargs):
        flujo = kwargs["flujo"]
        flujo["state"] = "onboarding_add_another_service"
        flujo["services"] = ["Plomeria", "Electricidad"]
        flujo["servicios_temporales"] = ["Plomeria", "Electricidad"]
        flujo["servicios_detallados"] = [
            {
                "raw_service_text": "Plomeria",
                "service_name": "Plomeria",
            },
            {
                "raw_service_text": "Electricidad",
                "service_name": "Electricidad",
            },
        ]
        return {
            "response": {"success": True, "messages": [{"response": "ok"}]},
            "new_flow": flujo,
            "persist_flow": True,
        }

    async def _fake_publicar_evento_onboarding(**_kwargs):
        return None

    async def _fake_establecer_flujo(*_args, **_kwargs):
        return None

    async def _fake_false(*_args, **_kwargs):
        return False

    async def _fake_alias(telefono):
        return telefono

    async def _fake_noop_response(*_args, **_kwargs):
        return None

    async def _fake_false_duplicate(*_args, **_kwargs):
        return False

    async def _fake_sync(flujo_anterior, flujo_actual, **_kwargs):
        llamadas_sync.append(
            (
                dict(flujo_anterior),
                dict(flujo_actual),
            )
        )
        return True

    monkeypatch.setattr(modulo_orquestacion, "obtener_flujo", _fake_obtener_flujo)
    monkeypatch.setattr(
        modulo_orquestacion,
        "obtener_perfil_proveedor_cacheado",
        _fake_obtener_perfil_proveedor_cacheado,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "obtener_vista_onboarding",
        _fake_obtener_vista_onboarding,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "manejar_mensaje",
        _fake_manejar_mensaje,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "sincronizar_servicios_si_cambiaron",
        _fake_sync,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "publicar_evento_onboarding",
        _fake_publicar_evento_onboarding,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "onboarding_async_persistence_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "establecer_flujo",
        _fake_establecer_flujo,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_hay_contexto_disponibilidad_activo",
        _fake_false,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_resolver_alias_disponibilidad",
        _fake_alias,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_registrar_respuesta_disponibilidad_si_aplica",
        _fake_noop_response,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "es_mensaje_multimedia_duplicado",
        _fake_false_duplicate,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "es_mensaje_interactivo_duplicado",
        _fake_false_duplicate,
    )

    solicitud = RecepcionMensajeWhatsApp(
        id="msg-2",
        phone="593959091325@s.whatsapp.net",
        from_number="593959091325@s.whatsapp.net",
        message="Servicios de jardinería y poda de árboles",
    )

    respuesta = asyncio.run(
        modulo_orquestacion.procesar_mensaje_whatsapp(
            solicitud=solicitud,
            supabase=object(),
            servicio_embeddings=None,
            cliente_openai=None,
            logger=types.SimpleNamespace(
                info=lambda *a, **k: None,
                warning=lambda *a, **k: None,
                debug=lambda *a, **k: None,
            ),
        )
    )

    assert respuesta["messages"][0]["response"] == "ok"
    assert llamadas_sync
    assert llamadas_sync[0][1]["state"] == "onboarding_add_another_service"
