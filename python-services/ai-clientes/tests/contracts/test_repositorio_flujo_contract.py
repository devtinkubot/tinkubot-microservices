"""Contract tests for IRepositorioFlujo implementations."""

import json

import pytest

from contracts.repositorios import IRepositorioFlujo
from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis
from models.estados import EstadoConversacion


class _MockRedis:
    def __init__(self) -> None:
        self._data = {}

    async def get(self, key: str):
        value = self._data.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def set(self, key: str, value, ex: int = None, expire: int = None):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        self._data[key] = value
        return True

    async def delete(self, key: str):
        self._data.pop(key, None)
        return 1


@pytest.fixture
def repo() -> RepositorioFlujoRedis:
    return RepositorioFlujoRedis(redis_cliente=_MockRedis())


@pytest.mark.asyncio
async def test_repositorio_flujo_cumple_contrato(repo: RepositorioFlujoRedis):
    assert isinstance(repo, IRepositorioFlujo)


@pytest.mark.asyncio
async def test_contrato_guardar_obtener_resetear(repo: RepositorioFlujoRedis):
    telefono = "+593990000001"

    await repo.guardar(
        telefono,
        {
            "telefono": telefono,
            "state": "awaiting_service",
            "service": "plomero",
        },
    )

    obtenido = await repo.obtener(telefono)
    assert obtenido.get("telefono") == telefono
    assert obtenido.get("service") == "plomero"

    await repo.resetear(telefono)
    reiniciado = await repo.obtener(telefono)
    assert reiniciado.get("telefono") == telefono
    assert reiniciado.get("state") == "awaiting_service"


@pytest.mark.asyncio
async def test_contrato_transicion_estado(repo: RepositorioFlujoRedis):
    telefono = "+593990000002"
    await repo.guardar(
        telefono,
        {
            "telefono": telefono,
            "state": "awaiting_service",
            "service": "electricista",
        },
    )

    flujo = await repo.transicionar_estado(
        telefono, EstadoConversacion.AWAITING_CITY
    )
    assert flujo is not None
    assert flujo.state == EstadoConversacion.AWAITING_CITY
