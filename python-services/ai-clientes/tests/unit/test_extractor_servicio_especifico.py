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
            '{"normalized_service":"elaboración de pliegos de contratación pública",'
            '"domain":"servicios legales",'
            '"category":"contratación pública",'
            '"service_summary":"Servicio de apoyo en contratación pública.",'
            '"confidence":0.88,'
            '"reason":"Servicio específico de contratación.",'
            '"status":"accepted"}',
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia(
        "necesito apoyo para levantar un pliegos de compras publicas para una contratacion de servicios profesionales"
    )

    assert perfil["normalized_service"] == "elaboración de pliegos de contratación pública"
    assert perfil["domain"] == "servicios legales"
    assert perfil["category"] == "contratación pública"
    profile = perfil["search_profile"]
    assert profile["primary_service"] == "elaboración de pliegos de contratación pública"
    assert profile["service_summary"] == "Servicio de apoyo en contratación pública."
    assert profile["domain"] == "servicios legales"
    assert profile["category"] == "contratación pública"
    assert profile["raw_input"].startswith("necesito apoyo")
    assert profile["source"] == "client"
    assert any(signal.startswith("servicio objetivo") for signal in profile["signals"])
    assert any("dominio" in signal for signal in profile["signals"])

    llamada_extraccion = fake.completions.llamadas[0]
    prompt_sistema = llamada_extraccion["messages"][0]["content"]
    assert "necesidades de clientes en Ecuador" in prompt_sistema
    assert "normalized_service" in prompt_sistema
    assert "category" in prompt_sistema
    assert "service_summary" in prompt_sistema
    assert "confidence" in prompt_sistema
    assert "status" in prompt_sistema


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


@pytest.mark.asyncio
async def test_extraer_servicio_generico_no_inventa_especialidad():
    fake = _FakeOpenAI(
        [
            '{"normalized_service":"carpintero","domain":"servicios del hogar",'
            '"category":"carpintería",'
            '"service_summary":"Servicio de carpintería.",'
            '"confidence":0.6,'
            '"reason":"Servicio genérico.",'
            '"status":"accepted"}'
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia("Necesito un carpintero")

    assert perfil["normalized_service"] == "carpintero"
    assert fake.completions.llamadas == []


@pytest.mark.asyncio
async def test_extraer_asesor_contable_usa_prompt_y_no_hint_local():
    fake = _FakeOpenAI(
        [
            '{"normalized_service":"asesoría contable","domain":"servicios contables",'
            '"category":"contabilidad",'
            '"service_summary":"Asesoría contable para negocios.",'
            '"confidence":0.9,'
            '"reason":"Servicio claro.",'
            '"status":"accepted"}'
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia("Necesito un asesor contable")

    assert perfil["normalized_service"] == "asesoría contable"
    assert perfil["domain"] == "servicios contables"
    assert perfil["category"] == "contabilidad"
    assert len(fake.completions.llamadas) == 1


@pytest.mark.asyncio
async def test_regla_local_mapea_reparacion_de_mueble_a_restauracion():
    fake = _FakeOpenAI(
        [
            '{"normalized_service":"restauración de muebles","domain":"construccion_hogar",'
            '"category":"restauración de muebles",'
            '"service_summary":"Servicio de restauración de muebles de madera.",'
            '"confidence":0.91,'
            '"reason":"La necesidad apunta a restauración, no a oficio genérico.",'
            '"status":"accepted"}'
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia(
        "Servicio de referencia: carpintero. Necesidad del usuario: arreglar un mueble de comedor"
    )

    assert perfil["normalized_service"] == "restauración de muebles"
    assert perfil["domain"] == "construccion_hogar"
    assert perfil["category"] == "restauración de muebles"
    assert len(fake.completions.llamadas) == 1


@pytest.mark.asyncio
async def test_regla_local_mapea_jardin_sucio_y_poda_a_mantenimiento():
    fake = _FakeOpenAI(
        [
            '{"normalized_service":"mantenimiento de jardines","domain":"jardinería",'
            '"category":"mantenimiento de jardines",'
            '"service_summary":"Servicio de mantenimiento y poda de jardines.",'
            '"confidence":0.93,'
            '"reason":"Servicio claramente relacionado con jardinería.",'
            '"status":"accepted"}'
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia(
        "El jardín de la casa está sucio y los árboles frutales necesitan poda, necesito que alguien me ayude."
    )

    assert perfil["normalized_service"] == "mantenimiento de jardines"
    assert perfil["domain"] == "jardinería"
    assert perfil["category"] == "mantenimiento de jardines"
    assert perfil["search_profile"]["service_summary"] == "Servicio de mantenimiento y poda de jardines."
    assert perfil["search_profile"]["primary_service"] == "mantenimiento de jardines"
    assert len(fake.completions.llamadas) == 1


@pytest.mark.asyncio
async def test_extraccion_reintenta_si_llega_incompleta_y_cierra_taxonomia():
    fake = _FakeOpenAI(
        [
            '{"normalized_service":"mantenimiento de jardines","domain":null,'
            '"category":null,'
            '"service_summary":"Servicio relacionado con jardines.",'
            '"confidence":0.62,'
            '"reason":"Falta precisión taxonómica.",'
            '"status":"clarification_required"}',
            '{"normalized_service":"mantenimiento de jardines","domain":"jardinería",'
            '"category":"mantenimiento de jardines",'
            '"service_summary":"Servicio de mantenimiento y poda de jardines.",'
            '"confidence":0.95,'
            '"reason":"Clasificación cerrada con precisión.",'
            '"status":"accepted"}',
        ]
    )
    extractor = ExtractorNecesidadIA(
        cliente_openai=fake,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=2.0,
        logger=logging.getLogger(__name__),
    )

    perfil = await extractor.extraer_servicio_con_ia(
        "Servicios de jardinería y poda de árboles"
    )

    assert perfil["normalized_service"] == "mantenimiento de jardines"
    assert perfil["domain"] == "jardinería"
    assert perfil["category"] == "mantenimiento de jardines"
    assert len(fake.completions.llamadas) == 2
