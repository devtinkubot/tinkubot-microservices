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
async def test_registrar_evento_taxonomia_runtime_inserta_evento_normalizado(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.metricas.run_supabase",
        _fake_run_supabase,
    )

    supabase = _SupabaseStub()
    resultado = await registrar_evento_taxonomia_runtime(
        supabase=supabase,
        source_channel="client",
        event_name="generic_fallback_used",
        domain_code="legal",
        fallback_source="fallback_hardcoded",
        service_text="Asesoría legal",
        context_excerpt="necesito ayuda legal",
        payload={"specificity": "insufficient"},
    )

    assert resultado["source_channel"] == "client"
    assert resultado["event_name"] == "generic_fallback_used"
    assert resultado["domain_code"] == "legal"
    assert resultado["fallback_source"] == "fallback_hardcoded"
    assert resultado["normalized_text"] == "asesoria legal"
    assert resultado["payload_json"] == {"specificity": "insufficient"}
