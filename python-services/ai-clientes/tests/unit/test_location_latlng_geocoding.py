"""Tests para resolución de ciudad desde lat/lng en flujo de clientes."""

from typing import Any, Dict, Optional

import pytest

from services.orquestador_conversacion import OrquestadorConversacional


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


@pytest.mark.asyncio
async def test_detectar_y_actualizar_ciudad_resuelve_por_lat_lng(monkeypatch):
    repo_clientes = _RepoClientesStub()
    orchestrator = OrquestadorConversacional(
        redis_client=None,
        supabase=None,
        gestor_sesiones=_GestorSesionesStub(),
        extractor_ia=_ExtractorIAStub(),
        repositorio_clientes=repo_clientes,
    )

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
    orchestrator = OrquestadorConversacional(
        redis_client=None,
        supabase=None,
        gestor_sesiones=_GestorSesionesStub(),
        extractor_ia=_ExtractorIAStub(),
        repositorio_clientes=repo_clientes,
    )
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

