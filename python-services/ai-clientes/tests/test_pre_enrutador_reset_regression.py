import pytest

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


class _LoggerStub:
    def info(self, *_args, **_kwargs):
        return None


class _OrquestadorResetStub:
    def __init__(self, flow, profile):
        self.repositorio_clientes = _RepoClientesStub(profile)
        self.repositorio_flujo = _RepoFlujoStub(flow)
        self.logger = _LoggerStub()
        self.servicio_consentimiento = None
        self._reset_called = False

    async def _sincronizar_cliente(self, flujo, perfil_cliente):
        return perfil_cliente.get("id")

    def _extraer_datos_mensaje(self, carga):
        texto = (carga.get("content") or "").strip()
        return texto, None, carga.get("message_type"), {}

    async def _detectar_y_actualizar_ciudad(self, *_args, **_kwargs):
        return None

    async def _procesar_comando_reinicio(self, telefono, _flujo, texto):
        if texto.lower() != "reset":
            return None
        self._reset_called = True
        # Simula persistencia de estado limpio hecha por la lógica real de reset.
        await self.repositorio_flujo.guardar(
            telefono,
            {
                "state": "awaiting_consent",
                "service_captured_after_consent": False,
            },
        )
        return {"messages": [{"response": "Nueva sesión iniciada."}]}


@pytest.mark.asyncio
async def test_reset_no_sobrescribe_estado_limpio_con_flujo_stale():
    stale_flow = {
        "state": "awaiting_service",
        "service": "electricista",
        "last_seen_at": "2026-02-24T17:25:30.034550",
        "last_seen_at_prev": "2026-02-24T17:01:15.349497",
    }
    profile = {"id": "c-reset", "has_consent": True, "city": "Cuenca"}
    orchestrator = _OrquestadorResetStub(stale_flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {"from_number": "+593700000001", "content": "Reset"},
    )

    assert orchestrator._reset_called is True
    assert result["response"]["messages"][0]["response"] == "Nueva sesión iniciada."
    assert orchestrator.repositorio_flujo.last_saved["state"] == "awaiting_consent"
    assert orchestrator.repositorio_flujo.last_saved["service_captured_after_consent"] is False

