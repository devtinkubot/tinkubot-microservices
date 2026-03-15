from flows.manejadores_estados.manejo_seleccion import (
    procesar_estado_presentando_resultados,
)
from templates.proveedores.listado import (
    construir_ui_lista_proveedores,
    mensaje_intro_listado_proveedores,
)


def test_mensaje_intro_listado_proveedores_usa_copy_nuevo():
    assert mensaje_intro_listado_proveedores("Cuenca") == "*Encontré estos expertos en Cuenca*"


def test_construir_ui_lista_proveedores_limita_a_cinco():
    proveedores = [{"id": f"prov-{idx}", "name": f"Proveedor {idx}"} for idx in range(1, 8)]

    ui = construir_ui_lista_proveedores(proveedores)

    assert ui["type"] == "list"
    assert ui["id"] == "provider_results_v1"
    assert ui["list_button_text"] == "Ver expertos"
    assert len(ui["options"]) == 5
    assert ui["options"][0]["id"] == "provider_select_prov-1"
    assert ui["options"][0]["title"] == "Proveedor 1"


async def _guardar_flujo_stub(_flujo):
    return None


async def _guardar_mensaje_stub(_mensaje):
    return None


async def _mensaje_conexion_stub(_proveedor):
    return {"response": "conexion"}


def _bloque_detalle_stub(proveedor):
    return f"Detalle {proveedor['name']}"


def _ui_detalle_stub(_proveedor):
    return {"type": "list", "id": "provider_detail_menu_v1"}


async def _preparar_detalle_stub(proveedor):
    preparado = dict(proveedor)
    preparado["face_photo_url"] = "https://example.com/foto-resuelta.jpg"
    return preparado


async def _programar_feedback_stub(_telefono, _proveedor):
    return None


import pytest


@pytest.mark.asyncio
async def test_presenting_results_acepta_interactive_list_reply():
    flujo = {
        "state": "presenting_results",
        "providers": [
            {"id": "prov-1", "name": "Diego Unkuch Gonzalez"},
            {"id": "prov-2", "name": "Proveedor Dos"},
        ],
    }
    guardado = {}

    async def _guardar(data):
        guardado.update(data)

    resultado = await procesar_estado_presentando_resultados(
        flujo=flujo,
        texto=None,
        seleccionado="provider_select_prov-1",
        telefono="593999111222",
        guardar_flujo_fn=_guardar,
        guardar_mensaje_bot_fn=_guardar_mensaje_stub,
        mensaje_conexion_formal_fn=_mensaje_conexion_stub,
        mensajes_confirmacion_busqueda_fn=lambda *args, **kwargs: [],
        programar_retroalimentacion_fn=_programar_feedback_stub,
        logger=None,
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        bloque_detalle_proveedor_fn=_bloque_detalle_stub,
        ui_detalle_proveedor_fn=_ui_detalle_stub,
        preparar_proveedor_detalle_fn=_preparar_detalle_stub,
        prompt_inicial="Prompt inicial",
        mensaje_despedida="Hasta luego",
    )

    assert guardado["state"] == "viewing_provider_detail"
    assert guardado["provider_detail_idx"] == 0
    assert guardado["provider_detail_view"] == "menu"
    assert guardado["providers"][0]["face_photo_url"] == "https://example.com/foto-resuelta.jpg"
    assert resultado["messages"][0]["response"] == "Detalle Diego Unkuch Gonzalez"
    assert resultado["messages"][0]["ui"] == {"type": "list", "id": "provider_detail_menu_v1"}


@pytest.mark.asyncio
async def test_presenting_results_con_texto_libre_reenvia_lista_interactiva():
    flujo = {
        "state": "presenting_results",
        "providers": [
            {"id": "prov-1", "name": "Diego Unkuch Gonzalez"},
            {"id": "prov-2", "name": "Proveedor Dos"},
        ],
    }

    resultado = await procesar_estado_presentando_resultados(
        flujo=flujo,
        texto="Hola",
        seleccionado=None,
        telefono="593999111222",
        guardar_flujo_fn=_guardar_flujo_stub,
        guardar_mensaje_bot_fn=_guardar_mensaje_stub,
        mensaje_conexion_formal_fn=_mensaje_conexion_stub,
        mensajes_confirmacion_busqueda_fn=lambda *args, **kwargs: [],
        programar_retroalimentacion_fn=_programar_feedback_stub,
        logger=None,
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        bloque_detalle_proveedor_fn=_bloque_detalle_stub,
        ui_detalle_proveedor_fn=_ui_detalle_stub,
        preparar_proveedor_detalle_fn=_preparar_detalle_stub,
        prompt_inicial="Prompt inicial",
        mensaje_despedida="Hasta luego",
    )

    assert resultado["response"] == "Selecciona un experto de la lista para ver su perfil."
    assert resultado["ui"]["type"] == "list"
    assert resultado["ui"]["id"] == "provider_results_v1"
