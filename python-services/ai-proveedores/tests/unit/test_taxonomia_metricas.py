from types import SimpleNamespace

import pytest

from services.taxonomia.metricas import registrar_evento_taxonomia_runtime


class _SupabaseInsertStub:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=[self.payload])


class _SupabaseStub:
    def __init__(self):
        self.query = _SupabaseInsertStub()

    def table(self, table_name: str):
        assert table_name == "service_taxonomy_runtime_events"
        return self.query


@pytest.mark.asyncio
async def test_registrar_evento_taxonomia_runtime_inserta_evento_provider(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.metricas.run_supabase",
        _fake_run_supabase,
    )

    supabase = _SupabaseStub()
    resultado = await registrar_evento_taxonomia_runtime(
        supabase=supabase,
        source_channel="provider",
        event_name="clarification_requested",
        domain_code="inmobiliario",
        fallback_source="taxonomy",
        service_text="servicio inmobiliario",
        context_excerpt="asesoria inmobiliaria",
        payload={"missing_dimensions": ["operacion"]},
    )

    assert resultado["source_channel"] == "provider"
    assert resultado["event_name"] == "clarification_requested"
    assert resultado["domain_code"] == "inmobiliario"
    assert resultado["fallback_source"] == "taxonomy"
    assert resultado["normalized_text"] == "servicio inmobiliario"
    assert resultado["payload_json"] == {"missing_dimensions": ["operacion"]}
