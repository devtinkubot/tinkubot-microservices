import pytest

from flows.mensajes import solicitar_ciudad
from flows.pre_enrutador import pre_enrutar_mensaje


class _RepoFlujoStub:
    def __init__(self, flow):
        self._flow = dict(flow)
        self.last_saved = None

    async def obtener(self, telefono: str):
        return dict(self._flow)

    async def guardar(self, telefono: str, flow):
        self.last_saved = dict(flow)


class _RepoClientesStub:
    def __init__(self, profile):
        self._profile = dict(profile)

    async def obtener_o_crear(self, telefono: str):
        return dict(self._profile)


class _OrquestadorStub:
    def __init__(self, flow, profile, consent_status="accepted"):
        self.repositorio_clientes = _RepoClientesStub(profile)
        self.repositorio_flujo = _RepoFlujoStub(flow)
        self.servicio_consentimiento = None
        self._consent_status = consent_status

    async def _validar_consentimiento(self, telefono, perfil_cliente, carga):
        return {"consent_status": self._consent_status}


@pytest.mark.asyncio
async def test_consent_accept_without_city_clears_stale_service_and_asks_city():
    stale_flow = {
        "state": "awaiting_city",
        "service": "plomero",
        "service_full": "necesito un plomero",
        "descripcion_problema": "fuga en cocina",
        "providers": [{"id": "p1"}],
        "searching_dispatched": True,
    }
    profile = {"id": "c1", "has_consent": False, "city": None}
    orchestrator = _OrquestadorStub(stale_flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {"from_number": "+593999", "content": "1"},
    )

    assert result["response"]["response"] == solicitar_ciudad()["response"]
    saved = orchestrator.repositorio_flujo.last_saved
    assert saved is not None
    assert saved["state"] == "awaiting_city"
    assert saved["service_captured_after_consent"] is False
    assert "service" not in saved
    assert "service_full" not in saved
    assert "descripcion_problema" not in saved
    assert "providers" not in saved
    assert "searching_dispatched" not in saved


@pytest.mark.asyncio
async def test_consent_accept_with_city_clears_stale_service_and_asks_service():
    stale_flow = {
        "state": "searching",
        "service": "electricista",
        "service_full": "electricista urgente",
        "descripcion_problema": "corte electrico",
    }
    profile = {"id": "c2", "has_consent": False, "city": "Cuenca"}
    orchestrator = _OrquestadorStub(stale_flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {"from_number": "+593888", "content": "1"},
    )

    assert isinstance(result["response"], str)
    saved = orchestrator.repositorio_flujo.last_saved
    assert saved is not None
    assert saved["state"] == "awaiting_service"
    assert saved["service_captured_after_consent"] is False
    assert "service" not in saved
    assert "service_full" not in saved
    assert "descripcion_problema" not in saved
