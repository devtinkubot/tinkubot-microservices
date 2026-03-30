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
                        "experience_range": "5 a 10 años",
                        "created_at": datetime(2026, 3, 8),
                        "services": ["capitan de barco"],
                        "matched_service_summary": "Servicio especializado en capitan de barco para embarcaciones turisticas.",
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
    assert "capitan de barco" in (providers[0].matched_service_summary or "").lower()
    assert providers[0].similarity_score == pytest.approx(0.88)


def test_build_effective_query_usa_contexto_canonico_sin_problema():
    service = SearchService()
    request = SimpleNamespace(
        query="capitan de barco",
        context={
            "problem_description": "Necesito un capitan de barco para una embarcacion turistica",
            "service_candidate": "capitan de barco",
            "domain": "transporte",
            "category": "navegación marítima",
        },
    )

    effective_query = service._build_effective_query(request)

    assert effective_query.startswith("capitan de barco transporte navegación marítima")
    assert (
        "Necesito un capitan de barco para una embarcacion turistica"
        not in effective_query
    )
    assert "capitan de barco" in effective_query


@pytest.mark.asyncio
async def test_search_by_embeddings_propagates_rpc_errors_without_fallback(monkeypatch):
    service = SearchService()
    service.supabase = object()

    async def fake_generate_embedding(_text):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(service, "_generate_embedding", fake_generate_embedding)

    class _RpcCall:
        def execute(self):
            raise RuntimeError("column p.experience_years does not exist")

    class _SupabaseStub:
        def rpc(self, fn_name, params):
            assert fn_name == "match_provider_services"
            return _RpcCall()

    service.supabase = _SupabaseStub()

    request = SimpleNamespace(
        query="arreglar aplicación móvil",
        limit=5,
        offset=0,
        filters=SimpleNamespace(city="Cuenca", verified_only=True),
    )

    with pytest.raises(RuntimeError, match="experience_years"):
        await service._search_by_embeddings(request, "arreglar aplicación móvil")


@pytest.mark.asyncio
async def test_search_by_embeddings_prioriza_coincidencia_semantica_sobre_ruido(
    monkeypatch,
):
    service = SearchService()
    service.supabase = object()

    async def fake_generate_embedding(_text):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(service, "_generate_embedding", fake_generate_embedding)

    class _RpcCall:
        def execute(self):
            return SimpleNamespace(
                data=[
                    {
                        "provider_id": "prov-tech",
                        "phone": "123",
                        "real_phone": "593999999999",
                        "full_name": "Proveedor Tech",
                        "city": "Cuenca",
                        "rating": 4.6,
                        "verified": True,
                        "experience_range": "5 a 10 años",
                        "created_at": datetime(2026, 3, 8),
                        "services": ["desarrollo de software"],
                        "matched_service_name": "desarrollo de software",
                        "matched_service_summary": "desarrollo de software a medida",
                        "domain_code": "tecnologia",
                        "category_name": "desarrollo de software",
                        "classification_confidence": 1.0,
                        "distance": 0.18,
                    },
                    {
                        "provider_id": "prov-noise",
                        "phone": "124",
                        "real_phone": "593999999998",
                        "full_name": "Proveedor Ruido",
                        "city": "Cuenca",
                        "rating": 5.0,
                        "verified": True,
                        "experience_range": "5 a 10 años",
                        "created_at": datetime(2026, 3, 8),
                        "services": ["renta de departamentos"],
                        "matched_service_name": "renta de departamentos",
                        "matched_service_summary": "gestión de arriendo y alquiler",
                        "domain_code": "inmobiliario",
                        "category_name": "gestión",
                        "classification_confidence": 1.0,
                        "distance": 0.05,
                    },
                ]
            )

    class _SupabaseStub:
        def rpc(self, fn_name, params):
            assert fn_name == "match_provider_services"
            return _RpcCall()

    service.supabase = _SupabaseStub()

    request = SimpleNamespace(
        query="desarrollo de aplicación móvil",
        context={
            "problem_description": "Necesito construir una aplicación móvil",
            "service_candidate": "desarrollo de aplicación móvil",
            "domain": "tecnología",
            "category": "desarrollo de software",
        },
        limit=5,
        offset=0,
        filters=SimpleNamespace(city="Cuenca", verified_only=True),
    )

    providers = await service._search_by_embeddings(
        request, "desarrollo de aplicación móvil"
    )

    assert providers[0].id == "prov-tech"
    assert providers[0].semantic_alignment_score is not None
    assert providers[1].semantic_alignment_score is not None
    assert providers[0].semantic_alignment_score > providers[1].semantic_alignment_score
    assert providers[0].matched_service_name == "desarrollo de software"
