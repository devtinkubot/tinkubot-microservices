import pytest

import flows.onboarding.handlers.ciudad as ciudad_handler
from templates.onboarding.ciudad import error_ciudad_multiple


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_autocorrige_y_avanza_estado():
    flujo = {"state": "onboarding_city"}
    respuesta = await ciudad_handler.manejar_espera_ciudad_onboarding(
        flujo, "Cuenca, Azuay, Ecuador"
    )

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "onboarding_dni_front_photo"


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_rechaza_provincia():
    flujo = {"state": "onboarding_city"}
    respuesta = await ciudad_handler.manejar_espera_ciudad_onboarding(flujo, "Azuay")

    assert respuesta["success"] is True
    assert flujo["state"] == "onboarding_city"
    assert "No reconocí esa ubicación" in respuesta["messages"][0]["response"]


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_prefiere_geocoding_sobre_parroquia(monkeypatch):
    flujo = {"state": "onboarding_city"}

    async def _resolver_ciudad_desde_coordenadas(_latitud: float, _longitud: float):
        return "Cuenca"

    monkeypatch.setattr(
        ciudad_handler,
        "_resolver_ciudad_desde_coordenadas",
        _resolver_ciudad_desde_coordenadas,
    )

    respuesta = await ciudad_handler.manejar_espera_ciudad_onboarding(
        flujo,
        "Paccha",
        carga={
            "location": {
                "latitude": -2.8987367153168,
                "longitude": -78.959991455078,
                "city": "Paccha",
                "address": "Paccha, Cuenca, Azuay, Ecuador",
            }
        },
    )

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "onboarding_dni_front_photo"


def test_error_ciudad_multiple_es_mas_claro_y_admite_ubicacion():
    mensaje = error_ciudad_multiple()

    assert "Solo necesitamos una ciudad principal." in mensaje
    assert "comparte tu ubicación" in mensaje
