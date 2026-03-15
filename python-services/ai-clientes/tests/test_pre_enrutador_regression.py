import pytest

from flows.mensajes import solicitar_ciudad
from flows.pre_enrutador import pre_enrutar_mensaje
from templates.mensajes.consentimiento import payload_consentimiento_resumen


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
        self.updated_city = None

    async def obtener_o_crear(self, telefono: str):
        return dict(self._profile)

    async def actualizar_ciudad(self, cliente_id: str, ciudad: str):
        self.updated_city = (cliente_id, ciudad)
        self._profile["city"] = ciudad
        self._profile["city_confirmed_at"] = "2026-02-28T00:00:00Z"
        return dict(self._profile)


class _ServicioConsentimientoStub:
    def __init__(self, *, consent_status="accepted"):
        self.calls = []
        self.consent_status = consent_status

    async def solicitar_consentimiento(self, telefono: str):
        payload = payload_consentimiento_resumen()
        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            return {"messages": payload["messages"]}
        return {"messages": [payload]}

    async def procesar_respuesta(self, telefono, perfil_cliente, seleccionado, carga):
        self.calls.append(
            {
                "telefono": telefono,
                "cliente_id": perfil_cliente.get("id"),
                "seleccionado": seleccionado,
                "content": carga.get("content"),
            }
        )
        return {"consent_status": self.consent_status}


class _OrquestadorStub:
    def __init__(self, flow, profile, consent_status="accepted"):
        self.repositorio_clientes = _RepoClientesStub(profile)
        self.repositorio_flujo = _RepoFlujoStub(flow)
        self.servicio_consentimiento = _ServicioConsentimientoStub(
            consent_status=consent_status
        )
        self._consent_status = consent_status
        self.logger = _LoggerStub()
        self.gestor_sesiones = _SesionStub()

    async def _validar_consentimiento(self, telefono, perfil_cliente, carga):
        return {"consent_status": self._consent_status}

    async def solicitar_consentimiento(self, telefono: str):
        payload = payload_consentimiento_resumen()
        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            return {"messages": payload["messages"]}
        return {"messages": [payload]}

    async def _sincronizar_cliente(self, *_args, **_kwargs):
        return "c-sync"

    def _extraer_datos_mensaje(self, carga):
        return (
            (carga.get("content") or "").strip(),
            (carga.get("selected_option") or "").strip(),
            (carga.get("message_type") or "").strip(),
            None,
        )

    async def _detectar_y_actualizar_ciudad(self, *_args, **_kwargs):
        return None

    async def _procesar_comando_reinicio(self, *_args, **_kwargs):
        return None


class _LoggerStub:
    def info(self, *_args, **_kwargs):
        return None


class _SesionStub:
    async def guardar_sesion(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_precontractual_first_touch_envia_session_first_y_prepara_awaiting_city(monkeypatch):
    monkeypatch.delenv("WA_ONBOARDING_STRATEGY", raising=False)
    monkeypatch.setenv("WA_ONBOARDING_IMAGE_URL", "https://example.com/onboarding.png")

    orchestrator = _OrquestadorStub(flow={}, profile={"id": "c1", "has_consent": False, "city": None})

    result = await pre_enrutar_mensaje(
        orchestrator,
        {"from_number": "+593999", "content": "hola"},
    )

    assert len(result["response"]["messages"]) == 1
    assert result["response"]["messages"][0]["ui"]["type"] == "buttons"
    assert result["response"]["messages"][0]["ui"]["header_type"] == "image"
    saved = orchestrator.repositorio_flujo.last_saved
    assert saved is not None
    assert saved["state"] == "awaiting_consent"
    assert saved["onboarding_intro_sent"] is True


@pytest.mark.asyncio
async def test_precontractual_continue_pide_ubicacion(monkeypatch):
    monkeypatch.delenv("WA_ONBOARDING_STRATEGY", raising=False)

    flow = {"state": "awaiting_city", "onboarding_intro_sent": True}
    profile = {"id": "c2", "has_consent": False, "city": None}
    orchestrator = _OrquestadorStub(flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {
            "from_number": "+593888",
            "selected_option": "continue_onboarding",
            "content": "",
        },
    )

    assert result["response"]["response"] == solicitar_ciudad()["response"]
    assert result["response"]["ui"]["type"] == "location_request"
    assert orchestrator.servicio_consentimiento.calls
    assert orchestrator.servicio_consentimiento.calls[0]["seleccionado"] == "1"


@pytest.mark.asyncio
async def test_precontractual_continue_con_ciudad_va_a_awaiting_service(monkeypatch):
    monkeypatch.delenv("WA_ONBOARDING_STRATEGY", raising=False)

    flow = {"state": "awaiting_city", "onboarding_intro_sent": True}
    profile = {"id": "c3", "has_consent": False, "city": "Cuenca"}
    orchestrator = _OrquestadorStub(flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {
            "from_number": "+593777",
            "selected_option": "continue_onboarding",
            "content": "",
        },
    )

    assert isinstance(result["response"], dict)
    assert "¿Qué necesitas resolver?" in result["response"]["response"]
    saved = orchestrator.repositorio_flujo.last_saved
    assert saved is not None
    assert saved["state"] == "awaiting_service"
    assert saved["has_consent"] is True
    assert saved["city"] == "Cuenca"


@pytest.mark.asyncio
async def test_precontractual_no_avanza_si_persistencia_consentimiento_falla(monkeypatch):
    monkeypatch.delenv("WA_ONBOARDING_STRATEGY", raising=False)

    flow = {"state": "awaiting_city", "onboarding_intro_sent": True}
    profile = {"id": "c5", "has_consent": False, "city": "Cuenca"}
    orchestrator = _OrquestadorStub(flow, profile, consent_status="error")

    result = await pre_enrutar_mensaje(
        orchestrator,
        {
            "from_number": "+593555",
            "selected_option": "continue_onboarding",
            "content": "",
        },
    )

    assert "messages" in result["response"]
    saved = orchestrator.repositorio_flujo.last_saved
    assert saved is not None
    assert saved["state"] == "awaiting_consent"
    assert saved["onboarding_intro_sent"] is True
    assert saved.get("has_consent") is not True


@pytest.mark.asyncio
async def test_consent_y_ciudad_existentes_no_reenvia_onboarding(monkeypatch):
    monkeypatch.delenv("WA_ONBOARDING_STRATEGY", raising=False)

    flow = {"state": "awaiting_service", "onboarding_intro_sent": False}
    profile = {"id": "c4", "has_consent": True, "city": "Quito"}
    orchestrator = _OrquestadorStub(flow, profile)

    result = await pre_enrutar_mensaje(
        orchestrator,
        {
            "from_number": "+593666",
            "content": "hola",
        },
    )

    assert "context" in result
    assert "response" not in result
