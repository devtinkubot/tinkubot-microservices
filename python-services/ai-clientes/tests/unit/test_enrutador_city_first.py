"""Tests para priorizar ciudad cuando el flujo aún no tiene estado."""

import pytest
from flows.enrutador import enrutar_estado
from flows.mensajes import solicitar_ciudad


class _RepoFlujoStub:
    def __init__(self):
        self.last_saved = None

    async def guardar(self, telefono: str, datos: dict):
        self.last_saved = (telefono, dict(datos))


class _GestorSesionesStub:
    async def guardar_sesion(self, telefono: str, texto: str, es_bot: bool):
        return None


class _OrquestadorStub:
    def __init__(self):
        self.repositorio_flujo = _RepoFlujoStub()
        self.gestor_sesiones = _GestorSesionesStub()

    async def guardar_flujo(self, telefono: str, datos: dict):
        return None


@pytest.mark.asyncio
async def test_estado_vacio_y_sin_ciudad_pide_ciudad_primero():
    orquestador = _OrquestadorStub()
    flujo = {}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000111",
        flujo=flujo,
        texto="necesito plomero urgente",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-1",
    )

    assert respuesta["response"] == solicitar_ciudad()["response"]
    assert flujo["state"] == "awaiting_city"
    assert flujo["city_confirmed"] is False

