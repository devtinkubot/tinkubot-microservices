"""Tests para la confirmación interactiva con botones del registro de proveedores."""

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

imghdr_stub: Any = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.proveedores import SolicitudCreacionProveedor  # noqa: E402
from services.onboarding.confirmacion import (  # noqa: E402
    _resolver_opcion_confirmacion,
    manejar_confirmacion_onboarding,
)
from templates.maintenance.confirmacion import (  # noqa: E402
    CONFIRM_ACCEPT_ID,
    CONFIRM_REJECT_ID,
    payload_confirmacion_resumen,
)


def test_payload_confirmacion_resumen_retorna_botones_interactivos():
    """Verifica que el payload de confirmación tiene estructura de botones."""
    resumen_test = "*Por favor confirma tus datos:*\n- Ciudad: Quito"
    payload = payload_confirmacion_resumen(resumen_test)

    assert "response" in payload
    assert "ui" in payload
    assert payload["response"] == resumen_test
    assert payload["ui"]["type"] == "buttons"
    assert payload["ui"]["id"] == "provider_registration_confirm_v1"
    assert payload["ui"]["footer_text"] == "¿Confirmas que los datos son correctos?"
    assert len(payload["ui"]["options"]) == 2

    # Verificar botón de aceptar
    accept_option = payload["ui"]["options"][0]
    assert accept_option["id"] == CONFIRM_ACCEPT_ID
    assert accept_option["title"] == "Acepto"

    # Verificar botón de rechazar
    reject_option = payload["ui"]["options"][1]
    assert reject_option["id"] == CONFIRM_REJECT_ID
    assert reject_option["title"] == "No acepto"


def test_resolver_opcion_confirmacion_acepta_boton_aceptar():
    """Verifica que el botón de aceptar se resuelve correctamente."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": CONFIRM_ACCEPT_ID,
            "content": "",
        }
    )

    assert opcion == "accept"


def test_resolver_opcion_confirmacion_acepta_boton_rechazar():
    """Verifica que el botón de rechazar se resuelve correctamente."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": CONFIRM_REJECT_ID,
            "content": "",
        }
    )

    assert opcion == "reject"


def test_resolver_opcion_confirmacion_fallback_texto_aceptar():
    """Verifica que el texto '1' se resuelve como aceptar."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": "",
            "content": "1",
        }
    )

    assert opcion == "accept"


def test_resolver_opcion_confirmacion_fallback_texto_rechazar():
    """Verifica que el texto '2' se resuelve como rechazar."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": "",
            "content": "2",
        }
    )

    assert opcion == "reject"


def test_resolver_opcion_confirmacion_fallback_si():
    """Verifica que el texto 'si' se resuelve como aceptar."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": "",
            "content": "si",
        }
    )

    assert opcion == "accept"


def test_resolver_opcion_confirmacion_fallback_editar():
    """Verifica que el texto 'editar' se resuelve como rechazar."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": "",
            "content": "quiero editar",
        }
    )

    assert opcion == "reject"


def test_resolver_opcion_confirmacion_retorna_none_si_no_reconoce():
    """Verifica que retorna None si no puede determinar la opción."""
    opcion = _resolver_opcion_confirmacion(
        {
            "selected_option": "",
            "content": "texto aleatorio",
        }
    )

    assert opcion is None


def test_constantes_ids_son_diferentes():
    """Verifica que los IDs de aceptar y rechazar son diferentes."""
    assert CONFIRM_ACCEPT_ID != CONFIRM_REJECT_ID
    assert CONFIRM_ACCEPT_ID == "confirm_accept"
    assert CONFIRM_REJECT_ID == "confirm_reject"


def test_confirmacion_onboarding_async_publica_evento_y_no_ejecuta_registro_sync(
    monkeypatch,
):
    flujo = {
        "state": "confirm",
        "phone": "593999111222@s.whatsapp.net",
        "provider_id": "prov-123",
        "services": ["electricidad"],
        "has_consent": True,
    }
    carga = {"selected_option": CONFIRM_ACCEPT_ID, "message_id": "msg-1"}
    datos_proveedor = SolicitudCreacionProveedor(
        phone="593999111222@s.whatsapp.net",
        full_name="",
        city="Quito",
        services_list=["electricidad"],
        has_consent=True,
        first_name="Proveedor",
        last_name="Test",
    )
    published = {}

    async def _registrar_no_usar(*_args, **_kwargs):
        raise AssertionError("No debe registrar síncronamente cuando async está activo")

    async def _subir_no_usar(*_args, **_kwargs):
        raise AssertionError(
            "No debe subir medios síncronamente cuando async está activo"
        )

    async def _publish_mock(**kwargs):
        published.update(kwargs)
        return "stream-1"

    async def _no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "services.onboarding.confirmacion.onboarding_async_persistence_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.onboarding.confirmacion.publicar_evento_onboarding",
        _publish_mock,
    )
    monkeypatch.setattr(
        "services.onboarding.confirmacion.reiniciar_flujo",
        _no_op,
    )
    monkeypatch.setattr(
        "services.onboarding.confirmacion.validar_y_construir_proveedor",
        lambda *_args, **_kwargs: (True, None, datos_proveedor),
    )

    respuesta = asyncio.run(
        manejar_confirmacion_onboarding(
            flujo=flujo,
            carga=carga,
            telefono="593999111222@s.whatsapp.net",
            registrar_proveedor_fn=_registrar_no_usar,
            subir_medios_fn=_subir_no_usar,
            logger=SimpleNamespace(
                info=lambda *a, **k: None, error=lambda *a, **k: None
            ),
        )
    )

    assert "Hola Proveedor Test" in respuesta["messages"][0]["response"]
    assert respuesta["new_flow"]["state"] == "pending_verification"
    assert (
        published["event_type"] == "provider.onboarding.registration.persist_requested"
    )
    assert published["payload"]["provider_data"]["first_name"] == "Proveedor"
    assert published["payload"]["provider_data"]["last_name"] == "Test"
    assert published["payload"]["provider_data"]["onboarding_complete"] is True
    assert "social_media_url" not in published["payload"]["provider_data"]
    assert "social_media_type" not in published["payload"]["provider_data"]
