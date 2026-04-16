import logging
from unittest.mock import AsyncMock

import pytest

from flows.enrutador import enrutar_estado


class _RepoFlujoStub:
    def __init__(self):
        self.last_saved = None

    async def guardar(self, telefono: str, datos: dict):
        self.last_saved = (telefono, dict(datos))


class _GestorSesionesStub:
    async def guardar_sesion(self, telefono: str, texto: str, es_bot: bool):
        return None


class _ServicioDisponibilidadStub:
    async def verificar_disponibilidad(self, **kwargs):
        return {"aceptados": [], "request_id": "req-123"}

    async def cerrar_solicitud(self, **kwargs):
        return None


class _OrquestadorStub:
    def __init__(self):
        self.repositorio_flujo = None
        self.gestor_sesiones = _GestorSesionesStub()
        self.logger = logging.getLogger("test-enrutador-no-disponibilidad")
        self.redis_client = AsyncMock()
        self.redis_client.get.return_value = None
        self.farewell_message = "Hasta luego"
        self.max_confirm_attempts = 3
        self.supabase = None
        self.buscador = None

    async def guardar_flujo(self, telefono: str, datos: dict):
        self._saved = (telefono, dict(datos))

    async def enviar_texto_whatsapp(self, telefono: str, mensaje: str, metadata=None):
        return True

    async def buscar_proveedores(self, servicio: str, ciudad: str, descripcion_problema: str | None = None):
        return {
            "ok": True,
            "providers": [{"id": "prov-1", "name": "Diego Unkuch Gonzalez", "phone_number": "593999111222"}],
            "total": 1,
        }

    async def enviar_prompt_confirmacion(self, telefono: str, data: dict, title: str):
        return {"messages": []}

    async def _procesar_searching(self, telefono: str, flujo: dict, do_search):
        return await do_search()


@pytest.mark.asyncio
async def test_searching_sin_aceptados_separa_mensaje_y_confirmacion(monkeypatch):
    servicio_stub = _ServicioDisponibilidadStub()
    monkeypatch.setattr(
        "flows.enrutador.servicio_disponibilidad",
        servicio_stub,
        raising=False,
    )
    monkeypatch.setattr(
        "services.proveedores.disponibilidad.servicio_disponibilidad",
        servicio_stub,
        raising=False,
    )
    monkeypatch.setattr(
        "principal.servicio_disponibilidad",
        servicio_stub,
        raising=False,
    )

    orquestador = _OrquestadorStub()
    flujo = {
        "state": "searching",
        "city": "Cuenca",
        "service": "desarrollo de aplicaciones móviles personalizadas",
        "service_full": "desarrollo de aplicaciones móviles personalizadas",
        "descripcion_problema": "necesito arreglar una app móvil del trabajo",
    }

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000777",
        flujo=flujo,
        texto="",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-7",
    )

    assert flujo["state"] == "confirm_new_search"
    assert (
        flujo["confirm_title"]
        == "*No hay expertos disponibles* para atender tu solicitud en *Cuenca*.\n\n"
        "*¿Te ayudo con otra solicitud o buscar expertos en otra ciudad?*"
    )
    assert len(respuesta["messages"]) == 1
    assert (
        respuesta["messages"][0]["response"]
        == "*No hay expertos disponibles* para atender tu solicitud en *Cuenca*.\n\n"
        "*¿Te ayudo con otra solicitud o buscar expertos en otra ciudad?*"
    )
