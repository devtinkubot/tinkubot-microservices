import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.review.progress import (  # noqa: E402
    inferir_checkpoint_onboarding_desde_perfil,
)


def test_inferir_checkpoint_revision_pendiente_usa_estado_canonico():
    perfil = {
        "id": "prov-1",
        "status": "pending",
        "onboarding_complete": True,
        "has_consent": True,
        "city": "Quito",
        "dni_front_photo_url": "https://example.com/dni-front.jpg",
        "face_photo_url": "https://example.com/face.jpg",
        "experience_range": "1-3",
        "services_list": ["Plomeria"],
    }

    assert (
        inferir_checkpoint_onboarding_desde_perfil(perfil)
        == "review_pending_verification"
    )
