"""Tests para UX de confirmación de nueva búsqueda."""

import pytest

from flows.manejadores_estados.manejo_confirmacion import (
    procesar_estado_confirmar_nueva_busqueda,
)
from templates.busqueda.confirmacion import mensajes_confirmacion_busqueda
from templates.proveedores.listado import mensaje_listado_sin_resultados


def test_mensaje_sin_resultados_usa_copy_directo():
    assert (
        mensaje_listado_sin_resultados("Cuenca")
        == "❌ *No* encontré expertos en *Cuenca*."
    )


def test_confirmacion_nueva_busqueda_con_ciudad_usa_botones():
    mensajes = mensajes_confirmacion_busqueda(
        "¿Te ayudo con otra solicitud?",
        incluir_opcion_ciudad=True,
    )

    assert len(mensajes) == 1
    assert mensajes[0]["response"] == "*¿Te ayudo con otra solicitud?*"
    assert mensajes[0]["ui"]["type"] == "buttons"
    assert [opt["id"] for opt in mensajes[0]["ui"]["options"]] == [
        "confirm_new_search_city",
        "confirm_new_search_service",
        "confirm_new_search_exit",
    ]


@pytest.mark.asyncio
async def test_confirmacion_nueva_busqueda_acepta_boton_buscar_otro_servicio():
    flujo = {
        "state": "confirm_new_search",
        "city": "Cuenca",
        "city_confirmed": True,
        "confirm_include_city_option": True,
    }

    async def resetear():
        return None

    async def responder(datos, respuesta):
        return {"flow": datos, **respuesta}

    async def reenviar():
        return {"response": "no deberia llamarse"}

    async def reenviar_confirmacion(_flujo, _titulo):
        return {"response": "no deberia llamarse"}

    async def guardar(_mensaje):
        return None

    resultado = await procesar_estado_confirmar_nueva_busqueda(
        flujo=flujo,
        texto=None,
        seleccionado="confirm_new_search_service",
        resetear_flujo_fn=resetear,
        responder_fn=responder,
        reenviar_proveedores_fn=reenviar,
        enviar_prompt_confirmacion_fn=reenviar_confirmacion,
        guardar_mensaje_bot_fn=guardar,
        prompt_inicial={
            "response": "¿Qué necesitas resolver?",
            "ui": {"type": "list"},
        },
        mensaje_despedida="Hasta luego",
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        max_intentos=3,
    )

    assert resultado["flow"]["state"] == "awaiting_service"
    assert resultado["response"] == "¿Qué necesitas resolver?"
    assert resultado["ui"]["type"] == "list"
