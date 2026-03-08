from datetime import datetime
from types import SimpleNamespace

import pytest

from services.search_service import SearchService


@pytest.mark.asyncio
async def test_search_by_embeddings_envia_threshold_y_mapea_resultados(monkeypatch):
    service = SearchService()
    service.supabase = object()

    monkeypatch.setattr(
        "services.search_service.settings.vector_similarity_threshold", 0.73
    )
    async def fake_generate_embedding(_text):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(service, "_generate_embedding", fake_generate_embedding)

    captured = {}

    async def fake_run_supabase(op, label):
        captured["label"] = label
        response = op()
        return response

    service._run_supabase = fake_run_supabase

    class _RpcCall:
        def execute(self):
            return SimpleNamespace(
                data=[
                    {
                        "provider_id": "prov-1",
                        "phone": "123",
                        "real_phone": "593999999999",
                        "full_name": "Proveedor Uno",
                        "city": "quito",
                        "rating": 4.8,
                        "verified": True,
                        "experience_years": 8,
                        "created_at": datetime(2026, 3, 8),
                        "services": ["capitan de barco"],
                        "distance": 0.12,
                    }
                ]
            )

    class _SupabaseStub:
        def rpc(self, fn_name, params):
            captured["fn_name"] = fn_name
            captured["params"] = params
            return _RpcCall()

    service.supabase = _SupabaseStub()

    request = SimpleNamespace(
        query="capitan de barco",
        limit=5,
        offset=0,
        filters=SimpleNamespace(city="quito", verified_only=True),
    )

    providers = await service._search_by_embeddings(request, "capitan de barco")

    assert captured["label"] == "providers.search_embeddings"
    assert captured["fn_name"] == "match_provider_services"
    assert captured["params"]["similarity_threshold"] == 0.73
    assert captured["params"]["city_filter"] == "%quito%"
    assert len(providers) == 1
    assert providers[0].id == "prov-1"
    assert providers[0].services == ["capitan de barco"]


def test_build_effective_query_preserva_contexto_existente():
    service = SearchService()
    request = SimpleNamespace(
        query="capitan de barco",
        context={
            "problem_description": "Necesito un capitan de barco para una embarcacion turistica",
            "service_candidate": "capitan de barco",
        },
    )

    effective_query = service._build_effective_query(request)

    assert "Necesito un capitan de barco para una embarcacion turistica" in effective_query
    assert "capitan de barco" in effective_query
