import pytest

from services.sesion_clientes import procesar_comando_reinicio


class _RepoFlujoStub:
    def __init__(self):
        self.was_reset = False
        self.last_saved = None

    async def resetear(self, telefono: str):
        self.was_reset = True

    async def guardar(self, telefono: str, flow):
        self.last_saved = dict(flow)


class _RepoClientesStub:
    def __init__(self):
        self.city_cleared_for = None
        self.consent_cleared_for = None

    async def limpiar_ciudad(self, cliente_id):
        self.city_cleared_for = cliente_id

    async def limpiar_consentimiento(self, cliente_id):
        self.consent_cleared_for = cliente_id


@pytest.mark.asyncio
async def test_reset_command_saves_clean_state_with_guard_flag_disabled():
    repo_flujo = _RepoFlujoStub()
    repo_clientes = _RepoClientesStub()

    result = await procesar_comando_reinicio(
        telefono="+593777",
        flujo={"customer_id": "cust-1", "service": "plomero"},
        texto="reset",
        repositorio_flujo=repo_flujo,
        resetear_flujo=None,
        guardar_flujo=None,
        repositorio_clientes=repo_clientes,
        limpiar_ciudad_cliente=lambda *_: None,
        limpiar_consentimiento_cliente=lambda *_: None,
        mensaje_nueva_sesion_dict=lambda: {"response": "Nueva sesión iniciada."},
        reset_keywords={"reset", "reiniciar"},
    )

    assert result == {"response": "Nueva sesión iniciada."}
    assert repo_flujo.was_reset is True
    assert repo_clientes.city_cleared_for == "cust-1"
    assert repo_clientes.consent_cleared_for == "cust-1"
    assert repo_flujo.last_saved == {
        "state": "awaiting_service",
        "service_captured_after_consent": False,
    }
