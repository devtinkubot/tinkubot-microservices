"""Tests para la compuerta de necesidad/problema en awaiting_service."""

import pytest
from flows.manejadores_estados.manejo_servicio import (
    procesar_estado_esperando_servicio,
)
from templates.mensajes.validacion import mensaje_error_input_sin_sentido


@pytest.mark.asyncio
async def test_rechazo_semantico_con_extraccion_pasa_a_confirmacion():
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

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "plomero"
    assert "Entendí que necesitas" in respuesta["response"]


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
    assert "Entendí que necesitas" in respuesta["response"]


@pytest.mark.asyncio
async def test_gate_v2_rechaza_pero_extrae_y_confirma():
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

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "servicio de capitán de embarcación"
    assert "Entendí que necesitas" in respuesta["response"]


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

    assert respuesta["response"] == mensaje_error_input_sin_sentido
    assert flujo_actualizado["state"] == "awaiting_service"
    assert "service_candidate" not in flujo_actualizado
