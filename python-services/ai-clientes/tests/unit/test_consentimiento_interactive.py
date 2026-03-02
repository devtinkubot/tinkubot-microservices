import pytest

from flows.mensajes.mensajes_busqueda import mensajes_consentimiento
from services.sesion_clientes import validar_consentimiento
from templates.mensajes.consentimiento import payload_consentimiento_resumen


class _ServicioConsentimientoSpy:
    def __init__(self):
        self.calls = []

    async def procesar_respuesta(self, telefono, perfil_cliente, seleccionado, carga):
        self.calls.append((telefono, seleccionado))
        return {"consent_status": "accepted" if seleccionado == "1" else "declined"}

    async def solicitar_consentimiento(self, telefono):
        payload = payload_consentimiento_resumen()
        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            return {"messages": payload["messages"]}
        return {"messages": [payload]}


@pytest.mark.asyncio
async def test_validar_consentimiento_mapea_interactive_accept():
    spy = _ServicioConsentimientoSpy()

    resultado = await validar_consentimiento(
        telefono="+593999",
        perfil_cliente={"id": "c1", "has_consent": False},
        carga={"selected_option": "consent_accept", "content": ""},
        servicio_consentimiento=spy,
        manejar_respuesta_consentimiento=None,
        solicitar_consentimiento=None,
        normalizar_boton_fn=lambda x: (x or "").strip().lower(),
        interpretar_si_no_fn=lambda x: None,
        opciones_consentimiento_textos=["Acepto", "No acepto"],
    )

    assert resultado["consent_status"] == "accepted"
    assert spy.calls == [("+593999", "1")]


@pytest.mark.asyncio
async def test_validar_consentimiento_mapea_interactive_decline():
    spy = _ServicioConsentimientoSpy()

    resultado = await validar_consentimiento(
        telefono="+593888",
        perfil_cliente={"id": "c2", "has_consent": False},
        carga={"selected_option": "consent_decline", "content": ""},
        servicio_consentimiento=spy,
        manejar_respuesta_consentimiento=None,
        solicitar_consentimiento=None,
        normalizar_boton_fn=lambda x: (x or "").strip().lower(),
        interpretar_si_no_fn=lambda x: None,
        opciones_consentimiento_textos=["Acepto", "No acepto"],
    )

    assert resultado["consent_status"] == "declined"
    assert spy.calls == [("+593888", "2")]


def test_payload_consentimiento_resumen_session_first(monkeypatch):
    monkeypatch.setenv("WA_ONBOARDING_IMAGE_URL", "https://example.com/onboarding.png")
    payload = payload_consentimiento_resumen()

    assert "messages" in payload
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["ui"]["type"] == "buttons"
    assert payload["messages"][0]["ui"]["header_type"] == "image"
    assert payload["messages"][0]["ui"]["header_media_url"] == "https://example.com/onboarding.png"
    assert payload["messages"][0]["ui"]["footer_text"] == "Al continuar aceptas nuestras condiciones."
    assert (
        payload["messages"][0]["response"]
        == "Para ayudarte a buscar expertos cercanos, usaré tu ubicación y tu necesidad para gestionar solicitudes en tiempo real.\n\nPolítica de privacidad:\nhttps://tinku.bot/privacy.html"
    )
    assert payload["messages"][0]["ui"]["options"][0]["id"] == "continue_onboarding"


def test_payload_consentimiento_footer_largo_se_recorta(monkeypatch):
    monkeypatch.setenv("WA_ONBOARDING_FOOTER_TEXT", "Al continuar aceptas el tratamiento de datos según nuestra política de privacidad vigente.")
    payload = payload_consentimiento_resumen()

    footer = payload["messages"][0]["ui"]["footer_text"]
    assert len(footer) == 60


def test_payload_consentimiento_footer_vacio_no_se_envia(monkeypatch):
    monkeypatch.setenv("WA_ONBOARDING_FOOTER_TEXT", "   ")
    payload = payload_consentimiento_resumen()

    assert "footer_text" not in payload["messages"][0]["ui"]

def test_mensajes_consentimiento_retorna_interactive():
    mensajes = mensajes_consentimiento()

    assert len(mensajes) == 1
    assert mensajes[0]["ui"]["type"] == "buttons"


def test_estrategia_invalida_hace_fallback_a_session_first(monkeypatch):
    monkeypatch.setenv("WA_ONBOARDING_STRATEGY", "flow_consent_v2")
    monkeypatch.setenv("WA_ONBOARDING_IMAGE_URL", "https://example.com/onboarding.png")

    payload = payload_consentimiento_resumen()

    assert payload["messages"][0]["ui"]["type"] == "buttons"
