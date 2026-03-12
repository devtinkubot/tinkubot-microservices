import pytest

from flows.manejadores_estados.manejo_confirmacion_servicio import (
    procesar_estado_confirmar_servicio,
)


@pytest.mark.asyncio
async def test_confirm_service_yes_sets_guard_flag_true():
    flujo = {
        "state": "confirm_service",
        "service_candidate": "plomero",
        "service_candidate_hint": "plomero",
        "service_candidate_hint_label": "plomero",
    }

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
    assert "service_candidate_hint" not in flujo


@pytest.mark.asyncio
async def test_confirm_service_accepts_interactive_yes_id():
    flujo = {"state": "confirm_service", "service_candidate": "electricista"}

    async def guardar(_):
        return None

    async def iniciar_busqueda(data):
        return {"response": f"ok:{data.get('service')}"}

    result = await procesar_estado_confirmar_servicio(
        flujo=flujo,
        texto=None,
        seleccionado="problem_confirm_yes",
        telefono="+593666",
        guardar_flujo_fn=guardar,
        iniciar_busqueda_fn=iniciar_busqueda,
        interpretar_si_no_fn=lambda _: None,
        mensaje_inicial_solicitud="¿Qué servicio necesitas?",
    )

    assert result == {"response": "ok:electricista"}
    assert flujo["service"] == "electricista"


@pytest.mark.asyncio
async def test_confirm_service_rejects_with_interactive_no_id():
    flujo = {
        "state": "confirm_service",
        "service_candidate": "electricista",
        "service_candidate_hint": "electricista",
    }

    async def guardar(_):
        return None

    async def iniciar_busqueda(_):
        return {"response": "no deberia llamarse"}

    result = await procesar_estado_confirmar_servicio(
        flujo=flujo,
        texto=None,
        seleccionado="problem_confirm_no",
        telefono="+593666",
        guardar_flujo_fn=guardar,
        iniciar_busqueda_fn=iniciar_busqueda,
        interpretar_si_no_fn=lambda _: None,
        mensaje_inicial_solicitud="¿Qué servicio necesitas?",
    )

    assert result == {"response": "¿Qué servicio necesitas?"}
    assert flujo["state"] == "awaiting_service"
    assert "service_candidate" not in flujo
    assert "service_candidate_hint" not in flujo


@pytest.mark.asyncio
async def test_confirm_service_invalid_choice_repeats_buttons_ui():
    flujo = {"state": "confirm_service", "service_candidate": "plomero"}

    async def guardar(_):
        return None

    async def iniciar_busqueda(_):
        return {"response": "no deberia llamarse"}

    result = await procesar_estado_confirmar_servicio(
        flujo=flujo,
        texto="tal vez",
        seleccionado=None,
        telefono="+593666",
        guardar_flujo_fn=guardar,
        iniciar_busqueda_fn=iniciar_busqueda,
        interpretar_si_no_fn=lambda _: None,
        mensaje_inicial_solicitud="¿Qué servicio necesitas?",
    )

    assert "Por favor confirma con un botón" in result["response"]
    assert result["ui"]["type"] == "buttons"
    assert [opt["id"] for opt in result["ui"]["options"]] == [
        "problem_confirm_yes",
        "problem_confirm_no",
    ]


@pytest.mark.asyncio
async def test_confirm_service_yes_normaliza_a_canonico_publicado():
    flujo = {"state": "confirm_service", "service_candidate": "laboralista"}

    async def guardar(_):
        return None

    async def iniciar_busqueda(data):
        return {"response": f"ok:{data.get('service')}"}

    async def resolver(servicio):
        assert servicio == "laboralista"
        return "abogado laboral"

    result = await procesar_estado_confirmar_servicio(
        flujo=flujo,
        texto="1",
        seleccionado=None,
        telefono="+593666",
        guardar_flujo_fn=guardar,
        iniciar_busqueda_fn=iniciar_busqueda,
        interpretar_si_no_fn=lambda _: True,
        mensaje_inicial_solicitud="¿Qué servicio necesitas?",
        resolver_servicio_canonico_fn=resolver,
    )

    assert result == {"response": "ok:abogado laboral"}
    assert flujo["service"] == "abogado laboral"
