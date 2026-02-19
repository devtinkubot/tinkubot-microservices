"""Tests para coordinador de búsqueda."""

from unittest.mock import AsyncMock

import pytest
from flows.busqueda_proveedores.coordinador_busqueda import (
    coordinar_busqueda_completa,
)


@pytest.mark.asyncio
async def test_no_inicia_busqueda_sin_servicio():
    guardar_flujo_callback = AsyncMock()
    enviar_mensaje_callback = AsyncMock(return_value=True)
    flujo = {"state": "awaiting_service", "service": "", "city": "Cuenca"}

    mensaje = await coordinar_busqueda_completa(
        telefono="+593999999999",
        flujo=flujo,
        enviar_mensaje_callback=enviar_mensaje_callback,
        guardar_flujo_callback=guardar_flujo_callback,
    )

    assert mensaje is None
    guardar_flujo_callback.assert_not_awaited()
