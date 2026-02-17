"""Tests del validador semántico necesidad/problema en extractor IA."""

import asyncio
import logging

import pytest

from services.extraccion.extractor_necesidad_ia import ExtractorNecesidadIA


@pytest.mark.asyncio
async def test_es_necesidad_fail_open_si_no_hay_openai():
    extractor = ExtractorNecesidadIA(
        cliente_openai=None,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=1.0,
        logger=logging.getLogger(__name__),
    )

    assert await extractor.es_necesidad_o_problema("plomero") is True


@pytest.mark.asyncio
async def test_es_necesidad_rechaza_texto_vacio():
    extractor = ExtractorNecesidadIA(
        cliente_openai=None,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=1.0,
        logger=logging.getLogger(__name__),
    )

    assert await extractor.es_necesidad_o_problema("   ") is False
