"""Tests para priorizar ciudad cuando el flujo aún no tiene estado."""

import logging

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


class _ExtractorIAStub:
    async def es_necesidad_o_problema(self, _texto: str) -> bool:
        return True

    async def extraer_servicio_con_ia(self, _texto: str) -> str:
        return "plomero"

    async def extraer_ubicacion_con_ia(self, _texto: str) -> str:
        return ""


class _OrquestadorStub:
    def __init__(self):
        self.repositorio_flujo = _RepoFlujoStub()
        self.gestor_sesiones = _GestorSesionesStub()
        self.extractor_ia = _ExtractorIAStub()
        self.repositorio_clientes = self
        self.greetings = {"hola", "buenas"}
        self.logger = logging.getLogger("test-enrutador-city-first")

    async def guardar_flujo(self, telefono: str, datos: dict):
        return None

    async def obtener_o_crear(self, telefono: str):
        return {
            "id": f"c-{telefono}",
            "city": "Cuenca",
            "city_confirmed_at": "2026-01-01T00:00:00",
        }

    async def obtener_o_crear_cliente(self, telefono: str):
        return await self.obtener_o_crear(telefono)

    async def enviar_texto_whatsapp(self, telefono: str, mensaje: str):
        return True

    async def construir_prompt_inicial_servicio(self):
        return {
            "response": "*¿Qué necesitas resolver?*. Describe lo que necesitas.",
            "ui": {
                "type": "list",
                "options": [
                    {"id": "popular_service::plomero", "title": "Plomero"},
                    {"id": "other_service", "title": "Otro servicio"},
                ],
            },
        }

    async def obtener_servicios_populares_recientes(self, limite: int = 5):
        return ["Plomero", "Electricista", "Cerrajero", "Limpieza del hogar", "Pintor"]


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


@pytest.mark.asyncio
async def test_estado_vacio_con_ciudad_pasa_por_confirm_service_y_no_busca_directo():
    orquestador = _OrquestadorStub()
    flujo = {"city": "Cuenca"}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000222",
        flujo=flujo,
        texto="necesito plomero urgente",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-2",
    )

    assert flujo["state"] == "confirm_service"
    assert flujo["service_candidate"] == "plomero"
    assert "service" not in flujo
    assert respuesta["ui"]["type"] == "buttons"
    assert [opt["id"] for opt in respuesta["ui"]["options"]] == [
        "problem_confirm_yes",
        "problem_confirm_no",
    ]


@pytest.mark.asyncio
async def test_estado_vacio_con_ciudad_y_saludo_va_directo_a_pregunta_servicio():
    orquestador = _OrquestadorStub()
    flujo = {"city": "Cuenca"}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000333",
        flujo=flujo,
        texto="hola",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-3",
    )

    assert flujo["state"] == "awaiting_service"
    assert "¿Qué necesitas resolver?" in respuesta["response"]
    assert respuesta["ui"]["type"] == "list"


@pytest.mark.asyncio
async def test_awaiting_service_list_reply_salta_confirmacion_y_busca_directo():
    orquestador = _OrquestadorStub()
    flujo = {"state": "awaiting_service", "city": "Cuenca"}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000444",
        flujo=flujo,
        texto="",
        seleccionado="popular_service::plomero",
        tipo_mensaje="interactive_list_reply",
        ubicacion={},
        cliente_id="cust-4",
    )

    assert flujo["state"] == "searching"
    assert flujo["service"] == "Plomero"
    assert "confirm_service" != flujo["state"]
    assert "buscando" in respuesta["response"].lower()


@pytest.mark.asyncio
async def test_awaiting_service_list_reply_otro_servicio_pide_texto_libre():
    orquestador = _OrquestadorStub()
    flujo = {"state": "awaiting_service", "city": "Cuenca"}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000555",
        flujo=flujo,
        texto="",
        seleccionado="other_service",
        tipo_mensaje="interactive_list_reply",
        ubicacion={},
        cliente_id="cust-5",
    )

    assert flujo["state"] == "awaiting_service"
    assert "Escribe el servicio que necesitas" in respuesta["response"]
