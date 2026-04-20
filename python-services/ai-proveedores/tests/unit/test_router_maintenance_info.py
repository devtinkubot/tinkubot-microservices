import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.maintenance.menu as modulo_menu  # noqa: E402
import flows.maintenance.views as modulo_views  # noqa: E402
import routes.maintenance.handlers.profile as modulo_profile  # noqa: E402
import routes.maintenance.info as modulo_info  # noqa: E402
from routes.maintenance import (  # noqa: E402
    manejar_informacion_personal_mantenimiento,
    manejar_informacion_profesional_mantenimiento,
)


def test_mantenimiento_info_personal_delega(monkeypatch):
    flujo = {"state": "maintenance_personal_info_action"}
    llamadas = []

    async def _fake_personal(**kwargs):
        llamadas.append(kwargs)
        return {"success": True, "messages": [{"response": "personal"}]}

    monkeypatch.setattr(
        modulo_info,
        "manejar_submenu_informacion_personal",
        _fake_personal,
    )

    resultado = asyncio.run(
        manejar_informacion_personal_mantenimiento(
            flujo=flujo,
            texto_mensaje="nombre",
            opcion_menu="1",
        )
    )

    assert resultado["success"] is True
    assert resultado["messages"][0]["response"] == "personal"
    assert llamadas[0]["flujo"] is flujo


def test_mantenimiento_info_profesional_delega(monkeypatch):
    flujo = {"state": "maintenance_professional_info_action"}
    llamadas = []

    async def _fake_profesional(**kwargs):
        llamadas.append(kwargs)
        return {"success": True, "messages": [{"response": "profesional"}]}

    monkeypatch.setattr(
        modulo_info,
        "manejar_submenu_informacion_profesional",
        _fake_profesional,
    )

    resultado = asyncio.run(
        manejar_informacion_profesional_mantenimiento(
            flujo=flujo,
            texto_mensaje="experiencia",
            opcion_menu="1",
        )
    )

    assert resultado["success"] is True
    assert resultado["messages"][0]["response"] == "profesional"
    assert llamadas[0]["flujo"] is flujo


def test_submenu_personal_muestra_solo_opciones_editables():
    payload = modulo_menu.payload_submenu_informacion_personal()

    opciones = payload["ui"]["options"]
    ids = [opcion["id"] for opcion in opciones]

    assert ids == [
        "provider_submenu_personal_ubicacion",
        "provider_submenu_personal_foto",
        "provider_submenu_personal_regresar",
    ]


def test_submenu_personal_acepta_texto_libre_y_regresa_menu():
    flujo = {"state": "maintenance_personal_info_action", "display_name": "Ana"}

    resultado_ubicacion = asyncio.run(
        modulo_menu.manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje="ubicacion",
            opcion_menu=None,
            selected_option=None,
        )
    )

    assert flujo["state"] == "viewing_personal_city"
    assert resultado_ubicacion["messages"][0]["ui"]["type"] == "buttons"

    resultado_menu = asyncio.run(
        modulo_menu.manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje="regresar",
            opcion_menu=None,
            selected_option=None,
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert resultado_menu["messages"][0]["ui"]["id"] == "provider_main_menu_v1"


def test_submenu_personal_bloquea_alias_legacy_de_datos_sensibles():
    flujo = {"state": "maintenance_personal_info_action", "display_name": "Ana"}

    resultado = asyncio.run(
        modulo_menu.manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje="cedula frontal",
            opcion_menu=None,
            selected_option="provider_submenu_personal_dni_frontal",
        )
    )

    assert flujo["state"] == "maintenance_personal_info_action"
    assert resultado["messages"][0]["ui"]["id"] == "provider_personal_info_menu_v1"


def test_submenu_profesional_acepta_texto_libre_y_regresa_menu():
    flujo = {"state": "maintenance_professional_info_action", "services": ["Plomeria"]}

    resultado_servicios = asyncio.run(
        modulo_menu.manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="servicios",
            opcion_menu=None,
            selected_option=None,
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert resultado_servicios["messages"][0]["ui"]["id"] == "provider_services_v2"

    resultado_menu = asyncio.run(
        modulo_menu.manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="regresar",
            opcion_menu=None,
            selected_option=None,
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert resultado_menu["messages"][0]["ui"]["id"] == "provider_main_menu_v1"


def test_submenu_servicios_reserva_ultima_fila_para_regresar():
    payload = modulo_views.payload_detalle_servicios(
        [f"Servicio {idx}" for idx in range(10)],
        10,
    )

    assert payload["response"] == (
        "Selecciona un servicio para ver, agregar, cambiar o eliminar."
    )
    opciones = payload["ui"]["options"]
    assert len(opciones) == 10
    assert opciones[-1]["id"] == "provider_service_back"
    assert opciones[-1]["title"] == "Regresar"


def test_detalle_servicio_vacio_usa_boton_agregar():
    payload = modulo_views.payload_detalle_servicio_individual(
        indice=2,
        servicio="",
        registrado=False,
    )

    assert "no tiene un servicio registrado" in payload["response"].lower()
    opciones = payload["ui"]["options"]

    assert opciones[0]["id"] == "provider_detail_service_change"
    assert opciones[0]["title"] == "Agregar"


def test_vista_servicios_acepta_regresar_por_texto_libre():
    flujo = {"state": "viewing_professional_services", "services": ["Plomeria"]}

    resultado = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_services",
            texto_mensaje="regresar",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_professional_info_action"
    assert resultado["messages"][0]["ui"]["id"] == "provider_professional_info_menu_v1"


def test_vista_servicios_texto_invalido_vuelve_menu_principal():
    flujo = {"state": "viewing_professional_services", "services": ["Plomeria"]}

    resultado = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_services",
            texto_mensaje="hola",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert resultado["messages"][0]["ui"]["id"] == "provider_main_menu_v1"


def test_vista_servicio_vacio_envia_prompt_en_messages(monkeypatch):
    flujo = {
        "state": "viewing_professional_service",
        "services": ["Plomeria"],
        "selected_service_index": 2,
    }

    async def _fake_prompt(**_kwargs):
        return {
            "response": "Escribe una habilidad o servicio que ofreces a tus clientes.",
            "ui": {
                "type": "buttons",
                "id": "provider_service_examples_v1",
                "options": [{"id": "a", "title": "Ejemplo"}],
            },
            "service_examples_lookup": {"a": {"title": "Ejemplo"}},
        }

    monkeypatch.setattr(
        modulo_views,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )

    resultado = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_service",
            texto_mensaje="provider_detail_service_change",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_service_add"
    assert flujo["profile_return_state"] == "viewing_professional_service"
    assert resultado["messages"][0]["response"].startswith("Escribe una habilidad")
    assert resultado["messages"][0]["ui"]["id"] == "provider_service_examples_v1"


def test_vista_servicio_eliminar_retorna_mismo_slot_vacio(monkeypatch):
    flujo = {
        "state": "viewing_professional_service",
        "services": [
            "Servicio 1",
            "Servicio 2",
            "Servicio 3",
            "Servicio 4",
            "Servicio 5",
            "Servicio 6",
        ],
        "selected_service_index": 5,
    }

    monkeypatch.setattr(
        modulo_views,
        "eliminar_servicio_proveedor",
        AsyncMock(
            return_value=[
                "Servicio 1",
                "Servicio 2",
                "Servicio 3",
                "Servicio 4",
                "Servicio 5",
            ]
        ),
    )

    resultado = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_service",
            texto_mensaje="provider_detail_service_delete",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "viewing_professional_service"
    assert flujo["selected_service_is_empty"] is True
    assert resultado["messages"][0]["ui"]["header_text"] == "Servicio 6"
    assert (
        "no tiene un servicio registrado"
        in resultado["messages"][0]["response"].lower()
    )
    assert [
        opcion["title"] for opcion in resultado["messages"][0]["ui"]["options"]
    ] == [
        "Agregar",
        "Regresar",
    ]


def test_vista_legacy_personal_sensible_redirige_a_submenu():
    flujo = {
        "state": "viewing_personal_name",
        "profile_edit_mode": "personal_name",
        "profile_return_state": "viewing_personal_name",
    }

    resultado = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_personal_name",
            texto_mensaje="provider_detail_name_change",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_personal_info_action"
    assert "profile_edit_mode" not in flujo
    assert "profile_return_state" not in flujo
    assert resultado["messages"][0]["ui"]["id"] == "provider_personal_info_menu_v1"


def test_handler_perfil_bloquea_estados_sensibles_de_maintenance():
    flujo = {
        "state": "maintenance_dni_back_photo_update",
        "maintenance_mode": True,
        "profile_edit_mode": "personal_dni_back_update",
        "profile_return_state": "viewing_personal_dni_back",
    }

    resultado = asyncio.run(
        modulo_profile.manejar_perfil_mantenimiento(
            flujo=flujo,
            estado="maintenance_dni_back_photo_update",
            texto_mensaje="cualquier cosa",
            carga={"image_base64": "back-image"},
            supabase=None,
            subir_medios_identidad=None,
            telefono="593999111299@s.whatsapp.net",
            cliente_openai=None,
        )
    )

    assert resultado is not None
    assert flujo["state"] == "maintenance_personal_info_action"
    assert "profile_edit_mode" not in flujo
    assert "profile_return_state" not in flujo
    assert (
        resultado["response"]["messages"][0]["ui"]["id"]
        == "provider_personal_info_menu_v1"
    )
