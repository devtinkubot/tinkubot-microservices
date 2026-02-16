import pytest

from flows.manejadores_estados.manejo_confirmacion_servicio import (
    procesar_estado_confirmar_servicio,
)


@pytest.mark.asyncio
async def test_confirm_service_yes_sets_guard_flag_true():
    flujo = {"state": "confirm_service", "service_candidate": "plomero"}

    async def guardar(_):
        return None

    async def iniciar_busqueda(data):
        return {"response": f"ok:{data.get('service')}"}

    result = await procesar_estado_confirmar_servicio(
        flujo=flujo,
        texto="1",
        seleccionado=None,
        telefono="+593666",
        guardar_flujo_fn=guardar,
        iniciar_busqueda_fn=iniciar_busqueda,
        interpretar_si_no_fn=lambda _: True,
        mensaje_inicial_solicitud="¿Qué servicio necesitas?",
    )

    assert result == {"response": "ok:plomero"}
    assert flujo["service"] == "plomero"
    assert flujo["service_captured_after_consent"] is True
    assert "service_candidate" not in flujo
