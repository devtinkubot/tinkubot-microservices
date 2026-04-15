import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.review.router as modulo_review  # noqa: E402


def test_revision_pendiente_no_muestra_menu():
    flujo = {
        "state": "review_pending_verification",
        "first_name": "Proveedor",
        "last_name": "En Revision",
    }

    respuesta = modulo_review.manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=None,
        provider_id=None,
    )

    assert respuesta is not None
    assert flujo["state"] == "review_pending_verification"
    assert len(respuesta["messages"]) == 1
    assert "revis" in respuesta["messages"][0]["response"].lower()
    assert "Proveedor En Revision" in respuesta["messages"][0]["response"]
    assert "ui" not in respuesta["messages"][0]


def test_revision_pendiente_desde_perfil_usa_estado_canonico():
    flujo = {
        "state": None,
        "first_name": "Proveedor",
        "last_name": "Pendiente",
    }
    perfil = {
        "id": "prov-1",
        "status": "pending",
        "onboarding_complete": True,
        "has_consent": True,
    }

    respuesta = modulo_review.manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=perfil,
        provider_id="prov-1",
    )

    assert respuesta is not None
    assert flujo["state"] == "review_pending_verification"
    assert "revis" in respuesta["messages"][0]["response"].lower()


def test_revision_legacy_pending_se_normaliza_a_review_pending():
    flujo = {
        "state": "pending_verification",
        "first_name": "Proveedor",
        "last_name": "Legacy",
    }

    respuesta = modulo_review.manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=None,
        provider_id=None,
    )

    assert respuesta is not None
    assert flujo["state"] == "review_pending_verification"


def test_revision_inicial_usa_first_name_y_last_name():
    flujo = {
        "state": None,
        "first_name": "Ana",
        "last_name": "Pérez",
    }

    respuesta = modulo_review.manejar_estado_revision_inicial(
        flujo=flujo,
        provider_id="prov-1",
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert "Ana Pérez" in respuesta["messages"][0]["response"]
