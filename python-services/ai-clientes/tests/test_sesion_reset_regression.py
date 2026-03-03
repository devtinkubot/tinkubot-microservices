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
        self.location_cleared_for = None
        self.consent_cleared_for = None
        self.lookup_phone = None
        self.last_consent_event = None

    async def limpiar_ciudad(self, cliente_id):
        self.city_cleared_for = cliente_id

    async def limpiar_ubicacion(self, cliente_id):
        self.location_cleared_for = cliente_id

    async def limpiar_consentimiento(self, cliente_id):
        self.consent_cleared_for = cliente_id

    async def obtener_o_crear(self, telefono: str):
        self.lookup_phone = telefono
        return {"id": "cust-from-phone", "phone_number": telefono}

    async def registrar_consentimiento(self, usuario_id, respuesta, datos_consentimiento):
        self.last_consent_event = {
            "usuario_id": usuario_id,
            "respuesta": respuesta,
            "datos_consentimiento": dict(datos_consentimiento or {}),
        }
        return True


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
    assert repo_clientes.location_cleared_for == "cust-1"
    assert repo_clientes.consent_cleared_for == "cust-1"
    assert repo_clientes.last_consent_event is not None
    assert repo_clientes.last_consent_event["usuario_id"] == "cust-1"
    assert repo_clientes.last_consent_event["respuesta"] == "declined"
    assert (
        repo_clientes.last_consent_event["datos_consentimiento"]["reason"] == "reset"
    )
    assert repo_flujo.last_saved == {
        "state": "awaiting_city",
        "onboarding_intro_sent": False,
    }


@pytest.mark.asyncio
async def test_only_reset_and_reiniciar_are_valid_reset_keywords():
    repo_flujo = _RepoFlujoStub()
    repo_clientes = _RepoClientesStub()

    result = await procesar_comando_reinicio(
        telefono="+593777",
        flujo={"customer_id": "cust-1"},
        texto="inicio",
        repositorio_flujo=repo_flujo,
        resetear_flujo=None,
        guardar_flujo=None,
        repositorio_clientes=repo_clientes,
        limpiar_ciudad_cliente=lambda *_: None,
        limpiar_consentimiento_cliente=lambda *_: None,
        mensaje_nueva_sesion_dict=lambda: {"response": "Nueva sesión iniciada."},
        reset_keywords={"reset", "reiniciar"},
    )

    assert result is None
    assert repo_flujo.was_reset is False


@pytest.mark.asyncio
async def test_reset_resolves_customer_by_phone_when_flow_has_no_customer_id():
    repo_flujo = _RepoFlujoStub()
    repo_clientes = _RepoClientesStub()

    result = await procesar_comando_reinicio(
        telefono="+593700000001",
        flujo={"service": "plomero"},
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
    assert repo_clientes.lookup_phone == "+593700000001"
    assert repo_clientes.city_cleared_for == "cust-from-phone"
    assert repo_clientes.location_cleared_for == "cust-from-phone"
    assert repo_clientes.consent_cleared_for == "cust-from-phone"
    assert repo_clientes.last_consent_event is not None
    assert repo_clientes.last_consent_event["usuario_id"] == "cust-from-phone"
    assert repo_clientes.last_consent_event["respuesta"] == "declined"
    assert (
        repo_clientes.last_consent_event["datos_consentimiento"]["reason"] == "reset"
    )
