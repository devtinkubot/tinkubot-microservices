"""Tests para extracción de servicio específico en extractor IA."""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from services.extraccion.extractor_necesidad_ia import ExtractorNecesidadIA


class _FakeCompletions:
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []

    async def create(self, **kwargs):
        self.llamadas.append(kwargs)
        contenido = self._respuestas.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=contenido),
                )
            ]
        )


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, respuestas):
        completions = _FakeCompletions(respuestas)
        self.chat = _FakeChat(completions)
        self.completions = completions


@pytest.mark.asyncio
async def test_prompt_extraccion_prioriza_servicio_especifico():
    fake = _FakeOpenAI(
        [
            "elaboracion de pliegos de contratacion publica",
            "elaboración de pliegos de contratación pública",
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    servicio = await extractor.extraer_servicio_con_ia(
        "necesito apoyo para levantar un pliegos de compras publicas para una contratacion de servicios profesionales"
    )

    assert servicio == "elaboración de pliegos de contratación pública"

    llamada_extraccion = fake.completions.llamadas[0]
    prompt_sistema = llamada_extraccion["messages"][0]["content"]
    assert "servicio MÁS ESPECÍFICO" in prompt_sistema
    assert "sobre categorías amplias" in prompt_sistema


@pytest.mark.asyncio
async def test_prompt_normalizacion_evita_generalizacion():
    fake = _FakeOpenAI(["elaboración de pliegos de contratación pública"])
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    servicio = await extractor._normalizar_servicio_a_espanol(
        "elaboracion de pliegos de contratacion publica"
    )

    assert servicio == "elaboración de pliegos de contratación pública"
    llamada_normalizacion = fake.completions.llamadas[0]
    prompt_sistema = llamada_normalizacion["messages"][0]["content"]
    assert "sin perder especificidad" in prompt_sistema
    assert "Evita generalizar" in prompt_sistema
