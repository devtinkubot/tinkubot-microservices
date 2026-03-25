import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import principal  # noqa: E402


def test_sesion_no_expira_con_inactividad_menor_al_umbral():
    ahora = datetime.now(timezone.utc)
    flujo = {
        "last_seen_at": (ahora - timedelta(minutes=10)).isoformat(),
    }

    assert (
        principal._sesion_expirada_por_inactividad(flujo, ahora) is False
    )


def test_sesion_expira_cuando_supera_el_umbral():
    ahora = datetime.now(timezone.utc)
    flujo = {
        "last_seen_at": (ahora - timedelta(hours=2)).isoformat(),
    }

    assert principal._sesion_expirada_por_inactividad(flujo, ahora) is True


def test_reanudacion_onboarding_ciudad_repite_mismo_paso():
    flujo = {"state": "onboarding_city"}

    resultado = principal._construir_reanudacion_onboarding(flujo)

    assert resultado["messages"][0]["response"].startswith("⌛ He detectado")
    assert resultado["messages"][1]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


def test_reanudacion_onboarding_dni_repite_cedula():
    flujo = {"state": "onboarding_dni_front_photo"}

    resultado = principal._construir_reanudacion_onboarding(flujo)

    assert resultado["messages"][1]["response"].startswith(
        "*Envía una foto frontal de tu cédula.*"
    )
