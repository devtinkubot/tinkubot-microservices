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

    async def create(self, **kwargs):
        if self.mode == "timeout":
            await asyncio.sleep(0.05)
            return _Response("[true]")
        if self.mode == "invalid_json":
            return _Response("no es json")
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
