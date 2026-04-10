# flake8: noqa
"""Regresiones de timeout para consentimiento/ciudad."""

import logging
from datetime import datetime, timedelta

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
        self.farewell_message = "Hasta luego"
        self.max_confirm_attempts = 3

    async def resetear_flujo(self, _telefono: str):
        return None

    async def guardar_flujo(self, _telefono: str, _datos: dict):
        return None

    async def solicitar_consentimiento(self, _telefono: str):
        return {"messages": [{"response": "CONSENT_PROMPT"}]}

    async def construir_prompt_inicial_servicio(self):
        return {
            "response": "*¿Qué necesitas resolver?*. Describe lo que necesitas.",
        }

    async def enviar_prompt_confirmacion(
        self, _telefono: str, _flujo: dict, titulo: str
    ):
        return {
            "response": f"*{titulo}*",
            "ui": {
                "type": "buttons",
                "options": [
                    {"id": "confirm_new_search_service", "title": "Nueva solicitud"},
                ],
            },
        }

    async def enviar_prompt_proveedor(self, _telefono: str, _flujo: dict, _ciudad: str):
        return {
            "response": "*Encontré estas opciones en Cuenca:*",
            "ui": {"type": "list", "id": "provider_results_v1"},
        }

    async def mensaje_conexion_formal(self, _proveedor: dict):
        return {"response": "conexion"}

    async def preparar_proveedor_para_detalle(self, proveedor: dict):
        return dict(proveedor)

    async def programar_solicitud_retroalimentacion(self, *args, **kwargs):
        return None


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


def _iso_minutes_from_now(minutes: int) -> str:
    return (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()


@pytest.mark.asyncio
async def test_listado_no_expira_con_deadline_vigente(monkeypatch):
    flow = {
        "state": "presenting_results",
        "city": "Cuenca",
        "providers": [{"id": "prov-1", "name": "Diego"}],
        "provider_results_expires_at": _iso_minutes_from_now(3),
        "last_seen_at_prev": _iso_minutes_from_now(-10),
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.repositorio_flujo.was_reset is False
    assert orquestador.repositorio_flujo.last_saved["state"] == "presenting_results"
    assert (
        respuesta["response"] == "Selecciona un experto de la lista para ver su perfil."
    )
    assert respuesta["ui"]["id"] == "provider_results_v1"


@pytest.mark.asyncio
async def test_listado_expirado_reinicia_con_prompt_inicial(monkeypatch):
    flow = {
        "state": "presenting_results",
        "city": "Cuenca",
        "providers": [{"id": "prov-1", "name": "Diego"}],
        "provider_results_expires_at": _iso_minutes_from_now(-1),
        "last_seen_at_prev": _iso_minutes_from_now(-10),
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.repositorio_flujo.last_saved["state"] == "confirm_new_search"
    assert respuesta["messages"][0]["response"] == "*¿Te ayudo con otro servicio?*"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"


@pytest.mark.asyncio
async def test_detalle_proveedor_expirado_reinicia_con_prompt_inicial(monkeypatch):
    flow = {
        "state": "viewing_provider_detail",
        "city": "Cuenca",
        "providers": [{"id": "prov-1", "name": "Diego"}],
        "provider_detail_idx": 0,
        "provider_results_expires_at": _iso_minutes_from_now(-1),
        "last_seen_at_prev": _iso_minutes_from_now(-10),
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.repositorio_flujo.last_saved["state"] == "confirm_new_search"
    assert respuesta["messages"][0]["response"] == "*¿Te ayudo con otro servicio?*"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"


@pytest.mark.asyncio
async def test_timeout_sin_consent_vuelve_a_consentimiento(monkeypatch):
    flow = {
        "state": "awaiting_consent",
        "last_seen_at_prev": _iso_minutes_from_now(-10),
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, False)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.repositorio_flujo.last_saved["state"] == "awaiting_consent"
    assert respuesta["messages"][0]["response"] == TIMEOUT_MSG
    assert respuesta["messages"][1]["response"] == "CONSENT_PROMPT"


@pytest.mark.asyncio
async def test_confirm_new_search_no_expira_por_timeout(monkeypatch):
    flow = {
        "state": "confirm_new_search",
        "city": "Cuenca",
        "confirm_include_city_option": True,
        "last_seen_at_prev": _iso_minutes_from_now(-10),
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, True)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.repositorio_flujo.was_reset is False
    assert orquestador.repositorio_flujo.last_saved["state"] == "confirm_new_search"
    assert respuesta["response"] == "*¿Te ayudo con otra solicitud?*"
    assert [opt["title"] for opt in respuesta["ui"]["options"]] == [
        "Nueva solicitud",
    ]
