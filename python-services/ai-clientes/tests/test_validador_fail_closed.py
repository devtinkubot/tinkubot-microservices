import asyncio
import logging

import pytest

from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA


class _Choice:
    def __init__(self, content: str):
        self.message = type("_Message", (), {"content": content})()


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, mode: str):
        self.mode = mode
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.mode == "timeout":
            await asyncio.sleep(0.05)
            return _Response("[true]")
        if self.mode == "invalid_json":
            return _Response("no es json")
        if self.mode == "retry_then_valid":
            if self.calls == 1:
                return _Response('{"results": [')
            return _Response(
                '{"results": [{"can_help": true, "confidence": 0.88, "reason": "coincidencia recuperada"}]}'
            )
        if self.mode == "structured_valid":
            return _Response(
                '[{"can_help": true, "confidence": 0.91, "reason": "experiencia directa"}]'
            )
        return _Response("[true]")


class _Chat:
    def __init__(self, mode: str):
        self.completions = _Completions(mode)


class _OpenAIStub:
    def __init__(self, mode: str):
        self.chat = _Chat(mode)


@pytest.mark.asyncio
async def test_validador_fail_closed_si_no_hay_openai_client():
    validador = ValidadorProveedoresIA(
        cliente_openai=None,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=0.01,
        logger=logging.getLogger("test"),
    )

    resultado = await validador.validar_proveedores(
        necesidad_usuario="microblading",
        descripcion_problema="microblading de cejas",
        proveedores=[{"id": "p1"}],
    )

    assert resultado == []


@pytest.mark.asyncio
async def test_validador_fail_closed_en_timeout_openai():
    validador = ValidadorProveedoresIA(
        cliente_openai=_OpenAIStub(mode="timeout"),
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=0.001,
        logger=logging.getLogger("test"),
    )

    resultado = await validador.validar_proveedores(
        necesidad_usuario="microblading",
        descripcion_problema="microblading de cejas",
        proveedores=[{"id": "p1"}],
    )

    assert resultado == []


@pytest.mark.asyncio
async def test_validador_fail_closed_en_json_invalido():
    validador = ValidadorProveedoresIA(
        cliente_openai=_OpenAIStub(mode="invalid_json"),
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=0.5,
        logger=logging.getLogger("test"),
    )

    resultado = await validador.validar_proveedores(
        necesidad_usuario="microblading",
        descripcion_problema="microblading de cejas",
        proveedores=[{"id": "p1"}],
    )

    assert resultado == []


@pytest.mark.asyncio
async def test_validador_acepta_respuesta_json_estructurada_y_no_falla_por_prompt():
    validador = ValidadorProveedoresIA(
        cliente_openai=_OpenAIStub(mode="structured_valid"),
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=0.5,
        logger=logging.getLogger("test"),
    )

    resultado = await validador.validar_proveedores(
        necesidad_usuario="desarrollo y mantenimiento de aplicaciones móviles",
        descripcion_problema="Qué alguien desarrolle la app movil y arregle los errores que tiene",
        proveedores=[
            {
                "id": "p1",
                "services_list": [
                    "desarrollo de aplicaciones móviles",
                    "desarrollo de software a medida",
                ],
                "experience_years": 5,
                "rating": 5,
            }
        ],
    )

    assert len(resultado) == 1
    assert resultado[0]["id"] == "p1"
    assert resultado[0]["validation_confidence"] == 0.91
    assert resultado[0]["validation_reason"] == "experiencia directa"


@pytest.mark.asyncio
async def test_validador_reintenta_si_openai_devuelve_json_malformado():
    validador = ValidadorProveedoresIA(
        cliente_openai=_OpenAIStub(mode="retry_then_valid"),
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=0.5,
        logger=logging.getLogger("test"),
    )

    resultado = await validador.validar_proveedores(
        necesidad_usuario="asesoría en contratación pública",
        descripcion_problema="Tengo un problema con contratación pública",
        proveedores=[
            {
                "id": "p1",
                "services_list": ["asesoría contratación pública"],
                "experience_years": 8,
                "rating": 5,
            }
        ],
    )

    assert len(resultado) == 1
    assert resultado[0]["validation_confidence"] == 0.88
