import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.gestores_estados.gestor_servicios as modulo_gestor_servicios
from flows.gestores_estados.gestor_servicios import (
    manejar_accion_servicios,
    manejar_accion_servicios_pendientes,
    manejar_seleccion_servicio_pendiente,
    manejar_confirmacion_precision_servicio_pendiente,
)


def test_selector_servicios_abre_submenu_activos():
    flujo = {"services": ["plomeria"], "generic_services_removed": ["transporte carga"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            opcion_menu="1",
        )
    )

    assert flujo["state"] == "awaiting_active_service_action"
    assert "Gestión de Servicios Activos" in respuesta["messages"][0]["response"]


def test_selector_servicios_abre_submenu_pendientes():
    flujo = {"services": ["plomeria"], "generic_services_removed": ["transporte carga"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="2",
            opcion_menu="2",
        )
    )

    assert flujo["state"] == "awaiting_pending_service_action"
    assert "Gestión de Servicios Pendientes" in respuesta["messages"][0]["response"]


def test_seleccion_pendiente_pide_precision():
    flujo = {"generic_services_removed": ["transporte carga", "asesoria legal"]}

    respuesta = asyncio.run(
        manejar_seleccion_servicio_pendiente(
            flujo=flujo,
            texto_mensaje="2",
        )
    )

    assert flujo["state"] == "awaiting_pending_service_add"
    assert flujo["pending_service_index"] == 1
    assert flujo["pending_service_original"] == "asesoria legal"
    assert "asesoria legal" in respuesta["messages"][0]["response"]


def test_confirmacion_pendiente_reemplaza_y_limpia_revision(monkeypatch):
    async def _actualizar_servicios(proveedor_id, servicios):
        return servicios

    async def _actualizar_pendientes(proveedor_id, pendientes):
        return pendientes

    monkeypatch.setattr(modulo_gestor_servicios, "actualizar_servicios", _actualizar_servicios)
    monkeypatch.setattr(
        modulo_gestor_servicios,
        "actualizar_servicios_pendientes_genericos",
        _actualizar_pendientes,
    )

    flujo = {
        "services": ["desarrollo de software"],
        "generic_services_removed": ["transporte carga"],
        "pending_service_index": 0,
        "service_add_temporales": ["transporte terrestre nacional de carga"],
        "service_review_required": True,
    }

    respuesta = asyncio.run(
        manejar_confirmacion_precision_servicio_pendiente(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_pending_service_action"
    assert flujo["services"] == [
        "desarrollo de software",
        "transporte terrestre nacional de carga",
    ]
    assert flujo["generic_services_removed"] == []
    assert flujo["service_review_required"] is False
    assert "transporte terrestre nacional de carga" in respuesta["messages"][0]["response"]


def test_confirmacion_pendiente_con_siete_activos_redirige_a_activos():
    flujo = {
        "services": [f"servicio {idx}" for idx in range(1, 8)],
        "generic_services_removed": ["transporte carga"],
        "pending_service_index": 0,
        "pending_service_original": "transporte carga",
        "service_add_temporales": ["transporte terrestre nacional de carga"],
        "service_review_required": True,
    }

    respuesta = asyncio.run(
        manejar_confirmacion_precision_servicio_pendiente(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_active_service_action"
    assert flujo["generic_services_removed"] == ["transporte carga"]
    assert flujo["service_add_temporales"] == ["transporte terrestre nacional de carga"]
    assert "primero elimina uno de tus servicios activos" in respuesta["messages"][0]["response"].lower()
    assert "Gestión de Servicios Activos" in respuesta["messages"][1]["response"]
