import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from flows.gestores_estados.gestor_espera_ciudad import (  # noqa: E402
    manejar_espera_ciudad,
)
from services.registro.normalizacion import (  # noqa: E402
    normalizar_datos_proveedor,
)
from services.registro.validacion_registro import (  # noqa: E402
    validar_y_construir_proveedor,
)
from templates.registro import solicitar_ciudad_registro  # noqa: E402


def test_solicitar_ciudad_registro_incluye_location_request():
    payload = solicitar_ciudad_registro()

    assert (
        payload["response"]
        == (
            "Ahora comparte tu *ubicación* para ubicar tu *ciudad*. "
            "Si prefieres, puedes escribir tu ciudad o una referencia cercana."
        )
    )
    assert payload["ui"]["type"] == "location_request"
    assert payload["ui"]["id"] == "provider_location_request_city_initial"


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_acepta_ubicacion_y_resuelve_ciudad(monkeypatch):
    async def _resolver(_lat, _lng):
        return "Cuenca"

    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_ciudad."
        "_resolver_ciudad_desde_coordenadas",
        _resolver,
    )

    flujo = {"state": "awaiting_city"}
    respuesta = await manejar_espera_ciudad(
        flujo,
        "",
        carga={"location": {"latitude": -2.9039, "longitude": -78.9838}},
        supabase=None,
        proveedor_id=None,
    )

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["location_lat"] == -2.9039
    assert flujo["location_lng"] == -78.9838
    assert flujo["state"] == "awaiting_dni_front_photo"
    assert "cédula" in respuesta["messages"][0]["response"].lower()
    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_dni_photo.png" in respuesta["messages"][0]["media_url"]


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_si_no_resuelve_repregunta_manual(monkeypatch):
    async def _resolver(_lat, _lng):
        return None

    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_ciudad."
        "_resolver_ciudad_desde_coordenadas",
        _resolver,
    )

    flujo = {"state": "awaiting_city"}
    respuesta = await manejar_espera_ciudad(
        flujo,
        "",
        carga={"location": {"latitude": -2.9039, "longitude": -78.9838}},
        supabase=None,
        proveedor_id=None,
    )

    assert flujo["state"] == "awaiting_city"
    assert respuesta["messages"][1]["ui"]["type"] == "location_request"
    assert (
        "No pude identificar la ciudad exacta"
        in respuesta["messages"][0]["response"]
    )


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_acepta_referencia_cercana_en_texto(monkeypatch):
    async def _resolver_texto(_texto):
        return "Cuenca"

    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_ciudad."
        "_resolver_ciudad_desde_texto",
        _resolver_texto,
    )

    flujo = {"state": "awaiting_city"}
    respuesta = await manejar_espera_ciudad(
        flujo,
        "Polideportivo de la ciudad",
        carga=None,
        supabase=None,
        proveedor_id=None,
    )

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "awaiting_dni_front_photo"


def test_validacion_registro_proveedor_preserva_coordenadas():
    flujo = {
        "name": "Proveedor Demo",
        "city": "Cuenca",
        "has_consent": True,
        "location_lat": -2.9039,
        "location_lng": -78.9838,
    }

    ok, error, proveedor = validar_y_construir_proveedor(
        flujo=flujo,
        telefono="593999999999@s.whatsapp.net",
    )

    assert ok is True
    assert error is None
    assert proveedor is not None
    assert proveedor.location_lat == -2.9039
    assert proveedor.location_lng == -78.9838


def test_validacion_registro_proveedor_agrega_timestamps_de_ubicacion():
    flujo = {
        "name": "Proveedor Demo",
        "city": "Cuenca",
        "has_consent": True,
        "location_lat": -2.9039,
        "location_lng": -78.9838,
    }

    ok, error, proveedor = validar_y_construir_proveedor(
        flujo=flujo,
        telefono="593999999999@s.whatsapp.net",
    )

    assert ok is True
    assert error is None
    assert proveedor is not None
    datos = normalizar_datos_proveedor(proveedor)

    assert datos["location_lat"] == -2.9039
    assert datos["location_lng"] == -78.9838
    assert datos["location_updated_at"] is not None
    assert datos["city_confirmed_at"] is not None
