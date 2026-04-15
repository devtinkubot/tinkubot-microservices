import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import services.shared.orquestacion_whatsapp as modulo_orquestacion  # noqa: E402
from models.mensajes import RecepcionMensajeWhatsApp  # noqa: E402


def test_orquestacion_mueve_menu_a_estado_canonico_de_disponibilidad(monkeypatch):
    estados_vistos = []
    flujos_persistidos = []

    async def _fake_obtener_flujo(_telefono):
        return {"state": "awaiting_menu_option", "has_consent": True}

    async def _fake_obtener_perfil_proveedor_cacheado(*_args, **_kwargs):
        return {"id": "prov-1", "has_consent": True}

    async def _fake_obtener_vista_onboarding(**kwargs):
        return {
            "flujo": kwargs["flujo"],
            "perfil_proveedor": kwargs["perfil_proveedor"],
        }

    async def _fake_hay_contexto(*_args, **_kwargs):
        return True

    async def _fake_alias(telefono):
        return telefono

    async def _fake_registrar(_telefono, _texto, estado_actual=None):
        estados_vistos.append(estado_actual)
        return {"success": True, "messages": [{"response": "registrado"}]}

    async def _fake_establecer_flujo(_telefono, flujo):
        flujos_persistidos.append(dict(flujo))
        return None

    async def _fake_false_duplicate(*_args, **_kwargs):
        return False

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
        "_hay_contexto_disponibilidad_activo",
        _fake_hay_contexto,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_resolver_alias_disponibilidad",
        _fake_alias,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "_registrar_respuesta_disponibilidad_si_aplica",
        _fake_registrar,
    )
    monkeypatch.setattr(
        modulo_orquestacion,
        "establecer_flujo",
        _fake_establecer_flujo,
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
        id="msg-av-1",
        phone="593959091325@s.whatsapp.net",
        from_number="593959091325@s.whatsapp.net",
        message="1",
    )

    respuesta = asyncio.run(
        modulo_orquestacion.procesar_mensaje_whatsapp(
            solicitud=solicitud,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            logger=types.SimpleNamespace(
                info=lambda *a, **k: None,
                warning=lambda *a, **k: None,
                debug=lambda *a, **k: None,
            ),
        )
    )

    assert respuesta["messages"][0]["response"] == "registrado"
    assert estados_vistos == ["availability_pending_response"]
    assert flujos_persistidos
    assert flujos_persistidos[0]["state"] == "awaiting_menu_option"
