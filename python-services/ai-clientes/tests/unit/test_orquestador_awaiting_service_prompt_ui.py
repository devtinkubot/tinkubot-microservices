"""Regresiones de UI list en awaiting_service para entradas no útiles."""

import pytest

from services.orquestador_conversacion import OrquestadorConversacional
from templates.mensajes.validacion import mensaje_error_input_invalido


class _ExtractorStub:
    async def extraer_servicio_con_ia_pura(self, _texto: str):
        return None

    async def es_necesidad_o_problema(self, _texto: str):
        return True


async def _responder(_flujo, respuesta):
    return respuesta


def _build_orquestador_stub():
    orquestador = OrquestadorConversacional.__new__(OrquestadorConversacional)
    orquestador.extractor_ia = _ExtractorStub()

    async def _verificar_no_bloqueado(_telefono: str):
        return False

    async def _sin_advertencias(_texto: str, _telefono: str):
        return None, None

    async def _prompt_lista():
        return {
            "response": "*¿Qué necesitas resolver?*. Puedes ver un *listado de servicios populares* o escribir directamente el *problema o necesidad*.",
            "ui": {"type": "list"},
        }

    orquestador.verificar_si_bloqueado = _verificar_no_bloqueado
    orquestador.validar_contenido_con_ia = _sin_advertencias
    orquestador.construir_prompt_inicial_servicio = _prompt_lista
    return orquestador


@pytest.mark.asyncio
async def test_awaiting_service_saludo_devuelve_prompt_con_lista():
    orquestador = _build_orquestador_stub()
    flujo = {"state": "awaiting_service"}

    respuesta = await orquestador._procesar_awaiting_service(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        texto="Hola",
        responder=_responder,
        cliente_id=None,
    )

    assert respuesta["ui"]["type"] == "list"
    assert "¿Qué necesitas resolver?" in respuesta["response"]


@pytest.mark.asyncio
async def test_awaiting_service_vacio_devuelve_prompt_con_lista():
    orquestador = _build_orquestador_stub()
    flujo = {"state": "awaiting_service"}

    respuesta = await orquestador._procesar_awaiting_service(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        texto="   ",
        responder=_responder,
        cliente_id=None,
    )

    assert respuesta["ui"]["type"] == "list"
    assert "¿Qué necesitas resolver?" in respuesta["response"]


@pytest.mark.asyncio
async def test_awaiting_service_numerico_invalido_mantiene_mensaje_corto_sin_ui():
    orquestador = _build_orquestador_stub()
    flujo = {"state": "awaiting_service"}

    respuesta = await orquestador._procesar_awaiting_service(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        texto="123",
        responder=_responder,
        cliente_id=None,
    )

    assert respuesta["response"] == mensaje_error_input_invalido
    assert "ui" not in respuesta
