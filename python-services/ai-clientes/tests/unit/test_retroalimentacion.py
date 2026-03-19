"""Regresiones para la retroalimentación de contratación."""

import logging

import pytest
from flows.enrutador import manejar_mensaje
from templates.mensajes.retroalimentacion import (
    mensaje_opcion_invalida_feedback,
    mensaje_solicitud_retroalimentacion,
    ui_retroalimentacion_contratacion,
)


class _RepoFlujoStub:
    def __init__(self):
        self.last_saved = None

    async def guardar(self, _telefono: str, datos: dict):
        self.last_saved = dict(datos)


class _OrquestadorStub:
    def __init__(self):
        self.repositorio_flujo = _RepoFlujoStub()
        self.logger = logging.getLogger("test-retroalimentacion")
        self.registros_feedback = []

    async def guardar_flujo(self, _telefono: str, _datos: dict):
        return None

    async def registrar_feedback_contratacion(
        self, *, lead_event_id: str, hired: bool, rating
    ):
        self.registros_feedback.append(
            {
                "lead_event_id": lead_event_id,
                "hired": hired,
                "rating": rating,
            }
        )


def _pre_enrutado(
    flow: dict, selected=None, text: str = "", msg_type: str = "interactive_list_reply"
):
    return {
        "context": {
            "phone": "593999111222@s.whatsapp.net",
            "flow": flow,
            "text": text,
            "selected": selected,
            "msg_type": msg_type,
            "location": {},
            "customer_id": "cust-1",
            "has_consent": True,
            "customer_city": "",
        }
    }


def test_mensaje_solicitud_retroalimentacion_incluye_copia_neutral():
    mensaje = mensaje_solicitud_retroalimentacion("Diego")
    ui = ui_retroalimentacion_contratacion("Diego")

    assert mensaje.startswith("*¿Cómo te fue con Diego?*")
    assert (
        "Calificar a nuestros expertos nos ayuda a mejorar el servicio "
        "que te entregamos." in mensaje
    )
    assert "Tu opinión hace la diferencia" in mensaje
    assert "*6.* Prefiero no responder" in mensaje
    assert "Por favor elige una opción de la lista." in mensaje
    assert [opt["id"] for opt in ui["options"]][-1] == "prefer_not_to_answer"
    assert ui["options"][-1]["title"] == "Prefiero no responder"
    assert "1 al 6" in mensaje_opcion_invalida_feedback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selected", "text"),
    [
        ("prefer_not_to_answer", ""),
        (None, "6"),
    ],
)
async def test_feedback_neutral_cierra_sin_registrar(selected, text, monkeypatch):
    flow = {
        "state": "awaiting_hiring_feedback",
        "pending_feedback_lead_event_id": "lead-1",
        "pending_feedback_provider_name": "Diego",
        "last_seen_at_prev": "2026-03-02T23:00:00",
    }

    async def _fake_pre(_orq, _carga):
        return _pre_enrutado(flow, selected=selected, text=text)

    monkeypatch.setattr("flows.enrutador.pre_enrutar_mensaje", _fake_pre)
    orquestador = _OrquestadorStub()

    respuesta = await manejar_mensaje(
        orquestador, {"from_number": "593999111222@s.whatsapp.net"}
    )

    assert orquestador.registros_feedback == []
    assert orquestador.repositorio_flujo.last_saved["state"] == "awaiting_service"
    assert (
        "pending_feedback_lead_event_id" not in orquestador.repositorio_flujo.last_saved
    )
    assert (
        respuesta["messages"][0]["response"]
        == "*¡Gracias por tu respuesta!* Tu feedback nos ayuda a mejorar."
    )
