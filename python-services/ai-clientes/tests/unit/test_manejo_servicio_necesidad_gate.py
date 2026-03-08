"""Tests para la compuerta de necesidad/problema en awaiting_service."""

import pytest
from flows.manejadores_estados.manejo_servicio import (
    procesar_estado_esperando_servicio,
)
from templates.mensajes.validacion import (
    mensaje_solicitar_detalle_servicio,
)


@pytest.mark.asyncio
async def test_rechazo_semantico_con_extraccion_pide_detalle_y_guarda_hint():
    flujo = {"state": "awaiting_service"}
    prompt = "¿Qué necesitas resolver?"

    async def extraer_fn(_texto: str):
        return "plomero"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="plomero",
        saludos=set(),
        prompt_inicial=prompt,
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert flujo_actualizado["service_candidate_hint"] == "plomero"
    assert flujo_actualizado["service_candidate_hint_label"] == "plomero"
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("plomero")
    assert "ui" not in respuesta


@pytest.mark.asyncio
async def test_acepta_necesidad_concreta_y_pasa_a_confirmacion():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "reparación de lavadoras"

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="mi lavadora no enciende",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "reparación de lavadoras"
    assert (
        flujo_actualizado["descripcion_problema"] == "mi lavadora no enciende"
    )
    assert "¿Es este el servicio que buscas:" in respuesta["response"]
    assert respuesta["ui"]["type"] == "buttons"


@pytest.mark.asyncio
async def test_gate_v2_rechaza_pero_extrae_y_pide_detalle():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "servicio de capitán de embarcación"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="capitan de barco",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert (
        flujo_actualizado["service_candidate_hint"]
        == "servicio de capitán de embarcación"
    )
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("capitan de barco")
    assert "ui" not in respuesta
    assert flujo_actualizado["service_candidate_hint_label"] == "capitan de barco"


@pytest.mark.asyncio
async def test_gate_v2_rechaza_y_sin_extraccion_bloquea():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return None

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="capitan de barco",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("capitan de barco")
    assert flujo_actualizado["state"] == "awaiting_service"
    assert "service_candidate" not in flujo_actualizado


@pytest.mark.asyncio
async def test_entrada_generica_usa_hint_limpio_y_no_repite_texto_crudo():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "carpintero"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="necesito un carpintero",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["service_candidate_hint"] == "carpintero"
    assert flujo_actualizado["service_candidate_hint_label"] == "carpintero"
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("carpintero")


@pytest.mark.asyncio
async def test_hint_previsto_se_combina_con_detalle_para_extraer_servicio():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "carpintero",
        "service_candidate_hint_label": "carpintero",
    }
    prompt = "¿Qué necesitas resolver?"
    llamadas = []

    async def extraer_fn(texto: str):
        llamadas.append(texto)
        return "fabricación de clóset a medida"

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="quiero hacer un clóset a medida para mi cuarto",
        saludos=set(),
        prompt_inicial=prompt,
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "fabricación de clóset a medida"
    assert "Servicio de referencia: carpintero." in llamadas[0]
    assert (
        flujo_actualizado["descripcion_problema"]
        == "Servicio de referencia: carpintero. Necesidad del usuario: quiero hacer un clóset a medida para mi cuarto"
    )
    assert "service_candidate_hint" not in flujo_actualizado
    assert "¿Es este el servicio que buscas:" in respuesta["response"]
