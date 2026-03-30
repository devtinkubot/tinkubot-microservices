"""Tests para priorizar ciudad cuando el flujo aún no tiene estado."""

import logging

import pytest
from flows.enrutador import _parece_nueva_solicitud_servicio, enrutar_estado
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

    async def resetear_flujo(self, telefono: str):
        return None

    async def obtener_o_crear(self, telefono: str):
        return {
            "id": f"c-{telefono}",
            "city": "Cuenca",
            "city_confirmed_at": "2026-01-01T00:00:00",
        }

    async def obtener_o_crear_cliente(self, telefono: str):
        return await self.obtener_o_crear(telefono)

    async def enviar_texto_whatsapp(
        self, telefono: str, mensaje: str, metadata: dict | None = None
    ):
        _ = metadata
        return True

    async def construir_prompt_inicial_servicio(self):
        return {
            "response": (
                "*¿Qué necesitas resolver?*. Describe lo que necesitas.\n"
                "Si no está en la lista, escríbelo directamente."
            ),
            "ui": {
                "type": "list",
                "options": [
                    {"id": "popular_service::plomero", "title": "Plomero"},
                ],
            },
        }

    async def obtener_servicios_populares_recientes(self, limite: int = 5):
        return ["Plomero", "Electricista", "Cerrajero", "Limpieza del hogar", "Pintor"]

    async def _procesar_awaiting_service(
        self, _telefono, flujo, texto, _responder, _cliente_id
    ):
        from flows.manejadores_estados.manejo_servicio import (
            procesar_estado_esperando_servicio,
        )

        return (
            await procesar_estado_esperando_servicio(
                flujo=flujo,
                texto=texto,
                saludos=self.greetings,
                prompt_inicial="*¿Qué necesitas resolver?*. Describe lo que necesitas.",
                extraer_fn=self.extractor_ia.extraer_servicio_con_ia,
                validar_necesidad_fn=self.extractor_ia.es_necesidad_o_problema,
            )
        )[1]


@pytest.mark.asyncio
async def test_detector_nueva_solicitud_ignora_si():
    orquestador = _OrquestadorStub()

    assert await _parece_nueva_solicitud_servicio(orquestador, "sí") is False


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
async def test_estado_vacio_con_ciudad_guarda_hint_y_pide_detalle():
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

    assert flujo["state"] == "awaiting_service"
    assert flujo["service_candidate_hint"] == "plomero"
    assert flujo["service_candidate_hint_label"] == "plomero"
    assert "para qué necesitas un *plomero*" in respuesta["response"].lower()
    assert "necesito plomero urgente" not in respuesta["response"].lower()
    assert "ui" not in respuesta


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
    assert "busco expertos" in respuesta["response"].lower()


@pytest.mark.asyncio
async def test_awaiting_service_texto_libre_sigue_flujo_normal():
    orquestador = _OrquestadorStub()
    flujo = {"state": "awaiting_service", "city": "Cuenca"}

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000555",
        flujo=flujo,
        texto="quiero pintar la sala de mi casa",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-5",
    )

    assert flujo["state"] == "confirm_service"
    assert flujo["descripcion_problema"] == "quiero pintar la sala de mi casa"
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_confirm_new_search_texto_nuevo_reinicia_busqueda():
    orquestador = _OrquestadorStub()
    orquestador.farewell_message = "Hasta luego"
    orquestador.max_confirm_attempts = 3
    flujo = {
        "state": "confirm_new_search",
        "city": "Cuenca",
        "city_confirmed": True,
    }

    llamado = {"hit": False}

    async def fake_procesar_awaiting_service(
        telefono, flujo_nuevo, texto, _responder, _cliente_id
    ):
        llamado["hit"] = True
        assert telefono == "+593999000666"
        assert flujo_nuevo["state"] == "awaiting_service"
        assert flujo_nuevo["city"] == "Cuenca"
        assert flujo_nuevo["city_confirmed"] is True
        assert texto == "necesito un asesor contable"
        return {"response": "RUTA NUEVA"}

    orquestador._procesar_awaiting_service = fake_procesar_awaiting_service

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000666",
        flujo=flujo,
        texto="necesito un asesor contable",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-6",
    )

    assert llamado["hit"] is True
    assert respuesta["response"] == "RUTA NUEVA"


@pytest.mark.asyncio
async def test_confirm_service_texto_nuevo_reinicia_busqueda():
    orquestador = _OrquestadorStub()
    orquestador.farewell_message = "Hasta luego"
    flujo = {
        "state": "confirm_service",
        "city": "Cuenca",
        "city_confirmed": True,
        "service_candidate": "plomero",
    }

    llamado = {"hit": False}

    async def fake_procesar_awaiting_service(
        telefono, flujo_nuevo, texto, _responder, _cliente_id
    ):
        llamado["hit"] = True
        assert telefono == "+593999000777"
        assert flujo_nuevo["state"] == "awaiting_service"
        assert flujo_nuevo["city"] == "Cuenca"
        assert texto == "necesito un asesor contable"
        return {"response": "RUTA NUEVA CONFIRM"}

    orquestador._procesar_awaiting_service = fake_procesar_awaiting_service

    respuesta = await enrutar_estado(
        orquestador,
        telefono="+593999000777",
        flujo=flujo,
        texto="necesito un asesor contable",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={},
        cliente_id="cust-7",
    )

    assert llamado["hit"] is True
    assert respuesta["response"] == "RUTA NUEVA CONFIRM"
