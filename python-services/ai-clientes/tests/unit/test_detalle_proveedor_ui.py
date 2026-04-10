# flake8: noqa
"""Tests para el detalle del proveedor."""

import pytest
from flows.manejadores_estados.manejo_detalle_proveedor import (
    procesar_estado_viendo_detalle_proveedor,
)
from services.proveedores.detalle import preparar_proveedor_para_detalle
from templates.proveedores.detalle import (
    DETALLE_PROVIDER_PHOTO,
    DETALLE_PROVIDER_SUBVIEW_BACK,
    bloque_detalle_proveedor,
    mensaje_servicios_proveedor,
    ui_detalle_proveedor,
)


def test_bloque_detalle_proveedor_usa_resumen_corto():
    mensaje = bloque_detalle_proveedor(
        {
            "name": "Diego Unkuch Gonzalez",
            "city": "Cuenca",
            "experience_range": "Más de 10 años",
            "rating": 5.0,
        }
    )

    assert mensaje == "\n".join(
        [
            "*Ubicación:* Cuenca",
            "*Experiencia:* Más de 10 años",
            "*Calificación:* 5.0",
        ]
    )


def test_ui_detalle_proveedor_usa_lista_dinamica():
    ui = ui_detalle_proveedor(
        {
            "full_name": "Diego Unkuch Gonzalez",
            "face_photo_url": "https://example.com/foto.jpg",
            "services": ["desarrollo de aplicaciones móviles"],
            "social_media_url": "https://linkedin.com/in/diego-unkuch",
            "certifications": [
                {"title": "AWS", "url": "https://example.com/aws.jpg"},
            ],
        }
    )

    assert ui["type"] == "list"
    assert ui["id"] == "provider_detail_menu_v1"
    assert ui["header_type"] == "text"
    assert ui["header_text"] == "Diego"
    assert "footer_text" not in ui
    assert ui["list_button_text"] == "Ver detalles"
    assert [opt["id"] for opt in ui["options"]] == [
        "provider_detail_photo",
        "provider_detail_services",
        "provider_detail_social",
        "provider_detail_certs",
        "provider_detail_contact",
        "provider_detail_back",
    ]


def test_mensaje_servicios_proveedor_incluye_boton_regresar():
    payload = mensaje_servicios_proveedor(
        {
            "name": "Diego Unkuch Gonzalez",
            "services": ["desarrollo de aplicaciones móviles"],
        }
    )

    assert "*Servicios que ofrece:*" in payload["response"]
    assert payload["ui"]["type"] == "buttons"
    assert payload["ui"]["options"][0]["id"] == "provider_detail_subview_back"


def test_preparar_proveedor_para_detalle_resuelve_url_y_limpia_query_vacia():
    proveedor = preparar_proveedor_para_detalle(
        {
            "face_photo_url": (
                "https://supabase.example/storage/v1/object/public/"
                "tinkubot-providers/faces/proveedor.jpg?"
            )
        },
        supabase=None,
        bucket="tinkubot-providers",
        supabase_base_url="https://supabase.example",
    )

    assert proveedor["face_photo_url"] == (
        "https://supabase.example/storage/v1/object/public/"
        "tinkubot-providers/faces/proveedor.jpg"
    )


async def _preparar_detalle_stub(proveedor):
    preparado = dict(proveedor)
    preparado["face_photo_url"] = "https://example.com/foto-resuelta.jpg"
    return preparado


@pytest.mark.asyncio
async def test_viewing_provider_detail_regresar_vuelve_al_listado():
    flujo = {
        "state": "viewing_provider_detail",
        "city": "Cuenca",
        "providers": [
            {"id": "prov-1", "name": "Diego Unkuch Gonzalez"},
        ],
        "provider_detail_idx": 0,
        "provider_detail_view": "menu",
    }
    guardado = {}

    async def _guardar_flujo(data):
        guardado.update(data)

    async def _guardar_mensaje(_mensaje):
        return None

    async def _mensaje_conexion(_proveedor):
        return {"response": "conexion"}

    async def _programar_feedback(_telefono, _proveedor, _lead_event_id):
        return None

    async def _reenviar_listado():
        return {
            "response": "*Encontré estos expertos en Cuenca*",
            "ui": {"type": "list"},
        }

    resultado = await procesar_estado_viendo_detalle_proveedor(
        flujo=flujo,
        texto=None,
        seleccionado="provider_detail_back",
        telefono="593999111222",
        guardar_flujo_fn=_guardar_flujo,
        guardar_mensaje_bot_fn=_guardar_mensaje,
        mensaje_conexion_formal_fn=_mensaje_conexion,
        mensajes_confirmacion_busqueda_fn=lambda *args, **kwargs: [],
        programar_retroalimentacion_fn=_programar_feedback,
        registrar_lead_contacto_fn=None,
        logger=None,
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        enviar_prompt_proveedor_fn=_reenviar_listado,
        prompt_inicial="Prompt inicial",
        mensaje_despedida="Hasta luego",
        ui_detalle_proveedor_fn=ui_detalle_proveedor,
        preparar_proveedor_detalle_fn=_preparar_detalle_stub,
    )

    assert guardado["state"] == "presenting_results"
    assert "provider_results_expires_at" in guardado
    assert "provider_detail_idx" not in guardado
    assert resultado["response"] == "*Encontré estos expertos en Cuenca*"
    assert resultado["ui"]["type"] == "list"


@pytest.mark.asyncio
async def test_viewing_provider_detail_foto_perfil_muestra_subvista():
    flujo = {
        "state": "viewing_provider_detail",
        "city": "Cuenca",
        "providers": [
            {"id": "prov-1", "name": "Diego Unkuch Gonzalez"},
        ],
        "provider_detail_idx": 0,
        "provider_detail_view": "menu",
    }
    guardado = {}

    async def _guardar_flujo(data):
        guardado.update(data)

    resultado = await procesar_estado_viendo_detalle_proveedor(
        flujo=flujo,
        texto=None,
        seleccionado=DETALLE_PROVIDER_PHOTO,
        telefono="593999111222",
        guardar_flujo_fn=_guardar_flujo,
        guardar_mensaje_bot_fn=lambda _mensaje: None,
        mensaje_conexion_formal_fn=lambda _proveedor: {"response": "conexion"},
        mensajes_confirmacion_busqueda_fn=lambda *args, **kwargs: [],
        programar_retroalimentacion_fn=None,
        registrar_lead_contacto_fn=None,
        logger=None,
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        enviar_prompt_proveedor_fn=lambda: {"response": "listado"},
        prompt_inicial="Prompt inicial",
        mensaje_despedida="Hasta luego",
        ui_detalle_proveedor_fn=ui_detalle_proveedor,
        preparar_proveedor_detalle_fn=_preparar_detalle_stub,
    )

    assert guardado["provider_detail_view"] == "photo"
    assert guardado["provider_results_expires_at"] is not None
    assert resultado["ui"]["type"] == "buttons"
    assert resultado["ui"]["options"][0]["id"] == DETALLE_PROVIDER_SUBVIEW_BACK


@pytest.mark.asyncio
async def test_viewing_provider_detail_regresar_en_subvista_vuelve_al_menu():
    flujo = {
        "state": "viewing_provider_detail",
        "city": "Cuenca",
        "providers": [
            {
                "id": "prov-1",
                "name": "Diego Unkuch Gonzalez",
                "services": ["desarrollo de aplicaciones móviles"],
            },
        ],
        "provider_detail_idx": 0,
        "provider_detail_view": "services",
    }
    guardado = {}

    async def _guardar_flujo(data):
        guardado.update(data)

    resultado = await procesar_estado_viendo_detalle_proveedor(
        flujo=flujo,
        texto=None,
        seleccionado=DETALLE_PROVIDER_SUBVIEW_BACK,
        telefono="593999111222",
        guardar_flujo_fn=_guardar_flujo,
        guardar_mensaje_bot_fn=lambda _mensaje: None,
        mensaje_conexion_formal_fn=lambda _proveedor: {"response": "conexion"},
        mensajes_confirmacion_busqueda_fn=lambda *args, **kwargs: [],
        programar_retroalimentacion_fn=None,
        registrar_lead_contacto_fn=None,
        logger=None,
        titulo_confirmacion_por_defecto="¿Te ayudo con otra solicitud?",
        enviar_prompt_proveedor_fn=lambda: {"response": "listado"},
        prompt_inicial="Prompt inicial",
        mensaje_despedida="Hasta luego",
        ui_detalle_proveedor_fn=ui_detalle_proveedor,
        preparar_proveedor_detalle_fn=_preparar_detalle_stub,
    )

    assert guardado["provider_detail_view"] == "menu"
    assert resultado["ui"]["type"] == "list"
    assert resultado["ui"]["id"] == "provider_detail_menu_v1"
