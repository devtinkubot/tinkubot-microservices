"""Tests para la compuerta de necesidad/problema en awaiting_service."""

import pytest

from flows.manejadores_estados.manejo_servicio import (
    procesar_estado_esperando_servicio,
)


@pytest.mark.asyncio
async def test_rechaza_profesion_aislada_y_repite_prompt():
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

    assert respuesta["response"] == prompt
    assert flujo_actualizado["state"] == "awaiting_service"
    assert "service_candidate" not in flujo_actualizado


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
