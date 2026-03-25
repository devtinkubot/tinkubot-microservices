import pytest

from flows.onboarding.handlers.ciudad import manejar_espera_ciudad_onboarding
from templates.onboarding.ciudad import error_ciudad_multiple


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_autocorrige_y_avanza_estado():
    flujo = {"state": "onboarding_city"}
    respuesta = await manejar_espera_ciudad_onboarding(
        flujo, "Cuenca, Azuay, Ecuador"
    )

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "onboarding_dni_front_photo"


@pytest.mark.asyncio
async def test_manejar_espera_ciudad_rechaza_provincia():
    flujo = {"state": "onboarding_city"}
    respuesta = await manejar_espera_ciudad_onboarding(flujo, "Azuay")

    assert respuesta["success"] is True
    assert flujo["state"] == "onboarding_city"
    assert "No reconocí esa ubicación" in respuesta["messages"][0]["response"]


def test_error_ciudad_multiple_es_mas_claro_y_admite_ubicacion():
    mensaje = error_ciudad_multiple()

    assert "Solo necesitamos una ciudad principal." in mensaje
    assert "comparte tu ubicación" in mensaje
