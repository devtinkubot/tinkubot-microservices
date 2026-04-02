import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import routes.review.router as modulo_review  # noqa: E402


def test_revision_pendiente_no_muestra_menu():
    flujo = {"state": "pending_verification", "full_name": "Proveedor En Revision"}

    respuesta = modulo_review.manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=None,
        provider_id=None,
    )

    assert respuesta is not None
    assert flujo["state"] == "pending_verification"
    assert len(respuesta["messages"]) == 1
    assert "revis" in respuesta["messages"][0]["response"].lower()
    assert "ui" not in respuesta["messages"][0]
