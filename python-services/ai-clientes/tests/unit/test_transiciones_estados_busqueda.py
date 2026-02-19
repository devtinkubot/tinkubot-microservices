"""Tests para transiciones de búsqueda con validación de servicio."""

import pytest
from flows.busqueda_proveedores.transiciones_estados import (
    verificar_ciudad_y_transicionar,
)
from templates.mensajes.validacion import mensaje_error_input_sin_sentido


@pytest.mark.asyncio
async def test_bloquea_transicion_si_falta_servicio():
    flujo = {"state": "awaiting_service", "service": ""}
    perfil_cliente = {"city": "Cuenca", "city_confirmed_at": "2026-02-19T15:00:00"}

    respuesta = await verificar_ciudad_y_transicionar(
        flujo=flujo,
        perfil_cliente=perfil_cliente,
    )

    assert respuesta["response"] == mensaje_error_input_sin_sentido
    assert flujo["state"] == "awaiting_service"
