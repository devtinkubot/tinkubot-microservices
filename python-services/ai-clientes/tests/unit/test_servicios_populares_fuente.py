"""Tests para fuente canónica de servicios populares."""

from types import SimpleNamespace

import pytest

from services.orquestador_conversacion import OrquestadorConversacional


class _SupabaseQueryStub:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _SupabaseStub:
    def __init__(self, data):
        self._data = data

    def table(self, table_name: str):
        assert table_name == "lead_events"
        return _SupabaseQueryStub(self._data)


class _GestorSesionesStub:
    pass


@pytest.mark.asyncio
async def test_populares_usa_lead_events_service_y_ordena_por_frecuencia(monkeypatch):
    data = [
        {"service": "Plomero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "electricista", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Plomero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Electricista", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Cerrajero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": " ", "created_at": "2026-03-01T00:00:00Z"},
    ]

    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.orquestador_conversacion.run_supabase",
        _fake_run_supabase,
    )

    orquestador = OrquestadorConversacional(
        redis_client=None,
        supabase=_SupabaseStub(data),
        gestor_sesiones=_GestorSesionesStub(),
        extractor_ia=object(),
    )

    populares = await orquestador.obtener_servicios_populares_recientes(limite=5)

    assert populares[:3] == ["electricista", "Plomero", "Cerrajero"]


@pytest.mark.asyncio
async def test_populares_si_falla_consulta_retorna_lista_vacia(monkeypatch):
    async def _fake_run_supabase(*_args, **_kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr(
        "services.orquestador_conversacion.run_supabase",
        _fake_run_supabase,
    )

    orquestador = OrquestadorConversacional(
        redis_client=None,
        supabase=_SupabaseStub([]),
        gestor_sesiones=_GestorSesionesStub(),
        extractor_ia=object(),
    )

    populares = await orquestador.obtener_servicios_populares_recientes(limite=5)

    assert populares == []
