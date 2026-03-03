"""Regresiones de timeout para consentimiento/ciudad."""

import logging

import pytest

from flows.enrutador import manejar_mensaje

TIMEOUT_MSG = "La sesión se reinició por *inactividad*. Continuemos."


class _RepoFlujoStub:
    def __init__(self):
        self.was_reset = False
        self.last_saved = None

    async def resetear(self, telefono: str):
        self.was_reset = True

    async def guardar(self, telefono: str, datos: dict):
        self.last_saved = dict(datos)


class _ConsentServiceStub:
    async def solicitar_consentimiento(self, _telefono: str):
        return {
            "messages": [
                {
                    "response": "CONSENT_PROMPT",
                    "ui": {"type": "buttons"},
                }
            ]
        }


class _OrquestadorStub:
    def __init__(self):
        self.repositorio_flujo = _RepoFlujoStub()
        self.servicio_consentimiento = _ConsentServiceStub()
        self.logger = logging.getLogger("test-timeout-consent")

    async def resetear_flujo(self, _telefono: str):
        return None

    async def guardar_flujo(self, _telefono: str, _datos: dict):
        return None

    async def solicitar_consentimiento(self, _telefono: str):
        return {"messages": [{"response": "CONSENT_PROMPT"}]}

    async def construir_prompt_inicial_servicio(self):
        return {
            "response": "*¿Qué necesitas resolver?*. Describe lo que necesitas.",
            "ui": {"type": "list"},
        }


def _pre_enrutado(flow: dict, has_consent: bool, customer_city: str = ""):
    return {
        "context": {
            "phone": "593999111222@s.whatsapp.net",
            "flow": flow,
            "text": "hola",
            "selected": None,
            "msg_type": "text",
            "location": {},
            "customer_id": "cust-1",
            "has_consent": has_consent,
            "customer_city": customer_city,
        }
    }


@pytest.mark.asyncio
async def test_timeout_con_consent_y_ciudad_va_awaiting_service(monkeypatch):
    flow = {
        "state": "presenting_results",
        "city": "Cuenca",
        "last_seen_at_prev": "2026-03-02T23:00:00",
    }
    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(orquestador, {"from_number": "593999111222@s.whatsapp.net"})

    assert orquestador.repositorio_flujo.was_reset is True
    assert orquestador.repositorio_flujo.last_saved["state"] == "awaiting_service"
    assert orquestador.repositorio_flujo.last_saved["city"] == "Cuenca"
    assert respuesta["messages"][0]["response"] == TIMEOUT_MSG
    assert "¿Qué necesitas resolver?" in respuesta["messages"][1]["response"]


@pytest.mark.asyncio
async def test_timeout_con_consent_sin_ciudad_va_awaiting_city(monkeypatch):
    flow = {
        "state": "presenting_results",
        "last_seen_at_prev": "2026-03-02T23:00:00",
    }
    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(orquestador, {"from_number": "593999111222@s.whatsapp.net"})

    assert orquestador.repositorio_flujo.last_saved["state"] == "awaiting_city"
    assert respuesta["messages"][0]["response"] == TIMEOUT_MSG
    assert "CONSENT_PROMPT" not in str(respuesta)
    assert respuesta["messages"][1]["ui"]["type"] == "location_request"


@pytest.mark.asyncio
async def test_timeout_sin_consent_vuelve_a_consentimiento(monkeypatch):
    flow = {
        "state": "awaiting_consent",
        "last_seen_at_prev": "2026-03-02T23:00:00",
    }
    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, False)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(orquestador, {"from_number": "593999111222@s.whatsapp.net"})

    assert orquestador.repositorio_flujo.last_saved["state"] == "awaiting_consent"
    assert respuesta["messages"][0]["response"] == TIMEOUT_MSG
    assert respuesta["messages"][1]["response"] == "CONSENT_PROMPT"
