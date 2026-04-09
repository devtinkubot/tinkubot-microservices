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
        filters=SimpleNamespace(city="quito"),
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
            "service_summary": "Capitan de barco para embarcaciones turísticas",
            "domain": "transporte",
            "category": "navegación marítima",
            "signals": ["requiere atención urgente", "servicio objetivo: capitan de barco"],
        },
    )

    effective_query = service._build_effective_query(request)

    assert effective_query.startswith(
        "Capitan de barco para embarcaciones turísticas transporte navegación marítima"
    )
    assert (
        "Necesito un capitan de barco para una embarcacion turistica"
        not in effective_query
    )
    assert "requiere atención urgente" not in effective_query
    assert "transporte" in effective_query
    assert "navegación marítima" in effective_query


def test_build_context_profile_incluye_signals_sin_alterar_query_canonica():
    service = SearchService()
    request = SimpleNamespace(
        query="reparación de lavadoras",
        context={
            "problem_description": "la lavadora no enciende",
            "service_candidate": "reparación de lavadoras",
            "service_summary": "Servicio de reparación de lavadoras con soporte a domicilio",
            "domain": "electrodomésticos",
            "category": "reparación de línea blanca",
            "signals": [
                "requiere atención urgente",
                "servicio objetivo: reparación de lavadoras",
            ],
        },
    )

    effective_query = service._build_effective_query(request)
    context_profile = service._build_context_profile(request)

    assert (
        effective_query
        == "Servicio de reparación de lavadoras con soporte a domicilio electrodomésticos reparación de línea blanca"
    )
    assert context_profile["signals_text"] == (
        "requiere atención urgente servicio objetivo: reparación de lavadoras"
    )
    assert "servicio" in context_profile["signals_tokens"]
    assert "reparacion" in context_profile["service_tokens"]


def test_generate_query_hash_incluye_signals_sin_modificar_query_base():
    service = SearchService()
    request_base = SimpleNamespace(
        query="capitan de barco transporte navegación marítima",
        filters=SimpleNamespace(city="quito", min_rating=0),
        context={
            "service_candidate": "capitan de barco",
            "domain": "transporte",
            "category": "navegación marítima",
        },
    )
    request_with_signals = SimpleNamespace(
        query="capitan de barco transporte navegación marítima",
        filters=SimpleNamespace(city="quito", min_rating=0),
        context={
            "service_candidate": "capitan de barco",
            "domain": "transporte",
            "category": "navegación marítima",
            "signals": ["requiere atención urgente", "servicio objetivo: capitan de barco"],
        },
    )

    hash_base = service._generate_query_hash(
        request_base, service._build_effective_query(request_base)
    )
    hash_signals = service._generate_query_hash(
        request_with_signals,
        service._build_effective_query(request_with_signals),
    )

    assert hash_base != hash_signals


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
        filters=SimpleNamespace(city="Cuenca"),
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
        filters=SimpleNamespace(city="Cuenca"),
    )

    providers = await service._search_by_embeddings(
        request, "desarrollo de aplicación móvil"
    )

    assert providers[0].id == "prov-tech"
    assert providers[0].semantic_alignment_score is not None
    assert providers[1].semantic_alignment_score is not None
    assert providers[0].semantic_alignment_score > providers[1].semantic_alignment_score
    assert providers[0].matched_service_name == "desarrollo de software"


@pytest.mark.asyncio
async def test_search_by_embeddings_prioriza_diego_sobre_proveedor_mas_rankeado(
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
                        "provider_id": "prov-augusto",
                        "phone": "123",
                        "real_phone": "593962765783",
                        "full_name": "Augusto Zhinin Matute",
                        "city": "Cuenca",
                        "rating": 5.0,
                        "experience_range": "5 a 10 años",
                        "created_at": datetime(2026, 3, 8),
                        "services": [
                            "mantenimiento de redes LAN",
                            "mantenimiento de redes WiFi",
                        ],
                        "matched_service_name": "mantenimiento de redes WiFi",
                        "matched_service_summary": "Servicio de mantenimiento y soporte para redes WiFi, asegurando su correcto funcionamiento y optimización.",
                        "domain_code": "tecnologia",
                        "category_name": "Tecnología",
                        "classification_confidence": 1.0,
                        "distance": 0.474877,
                    },
                    {
                        "provider_id": "prov-diego",
                        "phone": "124",
                        "real_phone": "593959091325",
                        "full_name": "",
                        "city": "Cuenca",
                        "rating": 0.0,
                        "experience_range": None,
                        "created_at": datetime(2026, 3, 8),
                        "services": [
                            "Desarrollo de aplicaciones móviles con inteligencia artificial",
                            "Gestión de proyectos de tecnología de la información y comunicación",
                        ],
                        "matched_service_name": "Desarrollo de aplicaciones móviles con inteligencia artificial",
                        "matched_service_summary": "Desarrollo de aplicaciones móviles que incorporan inteligencia artificial, incluyendo soporte y mantenimiento.",
                        "domain_code": "tecnologia",
                        "category_name": "Tecnología",
                        "classification_confidence": 1.0,
                        "distance": 0.417578,
                    },
                ]
            )

    class _SupabaseStub:
        def rpc(self, fn_name, params):
            assert fn_name == "match_provider_services"
            return _RpcCall()

    service.supabase = _SupabaseStub()

    request = SimpleNamespace(
        query="Se presento un problema en la app movil y necesito soporte y desarrollo",
        context={
            "problem_description": "Se presento un problema en la app movil y necesito soporte y desarrollo",
            "service_candidate": "soporte y desarrollo de app móvil",
            "service_summary": "Proveer soporte técnico y desarrollo para una aplicación móvil con problemas.",
            "domain": "tecnología",
            "category": "desarrollo de software",
        },
        limit=5,
        offset=0,
        filters=SimpleNamespace(city="Cuenca"),
    )

    providers = await service._search_by_embeddings(
        request, "soporte y desarrollo de app móvil"
    )

    assert providers[0].id == "prov-diego"
    assert providers[0].semantic_alignment_score > providers[1].semantic_alignment_score
