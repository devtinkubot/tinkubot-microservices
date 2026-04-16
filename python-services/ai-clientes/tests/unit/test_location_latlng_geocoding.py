"""Tests para resolución de ciudad desde lat/lng en flujo de clientes."""

from typing import Any, Dict, Optional

import pytest

from services.orquestador_conversacion import (
    OrquestadorConversacional,
    extraer_ciudad_desde_payload_ubicacion,
)


class _ExtractorIAStub:
    pass


class _GestorSesionesStub:
    async def guardar_sesion(self, *args, **kwargs):
        return None


class _RepoClientesStub:
    def __init__(self):
        self.location_updates = []
        self.city_updates = []

    async def obtener_o_crear(self, telefono: str):
        return {"id": "cust-1", "phone_number": telefono}

    async def actualizar_ubicacion(self, cliente_id: str, latitud: float, longitud: float):
        self.location_updates.append((cliente_id, latitud, longitud))
        return {"id": cliente_id, "location_lat": latitud, "location_lng": longitud}

    async def actualizar_ciudad(self, cliente_id: str, ciudad: str):
        self.city_updates.append((cliente_id, ciudad))
        return {
            "id": cliente_id,
            "city": ciudad,
            "city_confirmed_at": "2026-02-27T00:00:00",
        }


class _RepoFlujoStub:
    async def guardar(self, *args, **kwargs):
        return None


class _RepositorioLeadEventsStub:
    async def obtener_servicios_populares(self, *args, **kwargs):
        return []


class _CallbacksSourceStub:
    async def guardar_flujo(self, *args, **kwargs):
        return None

    async def limpiar_ubicacion_cliente(self, *args, **kwargs):
        return None

    async def limpiar_ciudad_cliente(self, *args, **kwargs):
        return None

    async def limpiar_consentimiento_cliente(self, *args, **kwargs):
        return None

    async def resetear_flujo(self, *args, **kwargs):
        return None

    async def solicitar_consentimiento(self, *args, **kwargs):
        return None

    async def enviar_texto_whatsapp(self, *args, **kwargs):
        return None


def _crear_orquestador(repo_clientes):
    return OrquestadorConversacional(
        redis_client=None,
        gestor_sesiones=_GestorSesionesStub(),
        buscador=object(),
        validador=object(),
        extractor_ia=_ExtractorIAStub(),
        servicio_consentimiento=object(),
        repositorio_flujo=_RepoFlujoStub(),
        repositorio_clientes=repo_clientes,
        repositorio_lead_events=_RepositorioLeadEventsStub(),
        callbacks_source=_CallbacksSourceStub(),
    )


@pytest.mark.asyncio
async def test_detectar_y_actualizar_ciudad_resuelve_por_lat_lng(monkeypatch):
    repo_clientes = _RepoClientesStub()
    orchestrator = _crear_orquestador(repo_clientes)

    async def _resolver(_lat: float, _lng: float) -> Optional[str]:
        return "Cuenca"

    monkeypatch.setattr(orchestrator, "_resolver_ciudad_desde_coordenadas", _resolver)

    flujo: Dict[str, Any] = {"customer_id": "cust-1"}
    await orchestrator._detectar_y_actualizar_ciudad(
        flujo=flujo,
        texto="",
        cliente_id="cust-1",
        perfil_cliente={},
        ubicacion={"latitude": -2.9039, "longitude": -78.9838},
    )

    assert repo_clientes.location_updates == [("cust-1", -2.9039, -78.9838)]
    assert repo_clientes.city_updates == [("cust-1", "Cuenca")]
    assert flujo["city"] == "Cuenca"
    assert flujo["city_confirmed"] is True


@pytest.mark.asyncio
async def test_awaiting_city_reusa_ciudad_confirmada_desde_ubicacion(monkeypatch):
    repo_clientes = _RepoClientesStub()
    orchestrator = _crear_orquestador(repo_clientes)
    orchestrator.enviar_texto_whatsapp = lambda *args, **kwargs: None
    orchestrator.guardar_flujo = lambda *args, **kwargs: None

    async def _transicion_stub(**kwargs):
        assert kwargs["ciudad_normalizada"] == "Cuenca"
        return {"messages": [{"response": "continuando flujo"}]}

    monkeypatch.setattr(
        "services.orquestador_conversacion.transicionar_a_busqueda_desde_ciudad",
        _transicion_stub,
    )

    async def _responder(_flujo, respuesta):
        return respuesta

    async def _guardar_mensaje_bot(_mensaje):
        return None

    flujo = {
        "state": "awaiting_city",
        "city": "Cuenca",
        "city_confirmed": True,
        "service": "plomero",
        "customer_id": "cust-1",
    }

    resultado = await orchestrator._procesar_awaiting_city(
        telefono="+593999111222",
        flujo=flujo,
        texto="",
        ubicacion={"latitude": -2.9039, "longitude": -78.9838},
        responder=_responder,
        guardar_mensaje_bot=_guardar_mensaje_bot,
    )

    assert resultado["messages"][0]["response"] == "continuando flujo"


def test_extraer_ciudad_desde_payload_prefiere_canton_cuando_ciudad_no_es_canonica():
    ubicacion = {
        "city": "Paccha",
        "address": "Paccha, Cuenca, Azuay, Ecuador",
        "name": "Paccha",
    }

    assert extraer_ciudad_desde_payload_ubicacion(ubicacion) == "Cuenca"


@pytest.mark.asyncio
async def test_resolver_ciudad_desde_coordenadas_prefiere_county_sobre_municipality(
    monkeypatch,
):
    repo_clientes = _RepoClientesStub()
    orchestrator = _crear_orquestador(repo_clientes)

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "address": {
                    "municipality": "Paccha",
                    "county": "Cuenca",
                },
                "display_name": "Paccha, Cuenca, Azuay, Ecuador",
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(
        "services.orquestador_conversacion.httpx.AsyncClient", _FakeClient
    )

    ciudad = await orchestrator._resolver_ciudad_desde_coordenadas(
        -2.8987367153168,
        -78.959991455078,
    )

    assert ciudad == "Cuenca"
