import logging
from unittest.mock import AsyncMock

import pytest
from services.buscador.buscador_proveedores import BuscadorProveedores


@pytest.mark.asyncio
async def test_buscador_usa_search_candidate_limit(monkeypatch):
    monkeypatch.setattr(
        "services.buscador.buscador_proveedores.configuracion.search_candidate_limit",
        15,
    )

    cliente_busqueda = AsyncMock()
    cliente_busqueda.buscar_proveedores = AsyncMock(
        return_value={
            "ok": True,
            "providers": [
                {
                    "id": "prov-1",
                    "first_name": "Proveedor",
                    "last_name": "Uno",
                    "services": ["capitan de barco"],
                    "similarity_score": 0.51,
                }
            ],
            "total": 1,
            "search_metadata": {"strategy": "embeddings", "search_time_ms": 250},
        }
    )
    validador_ia = AsyncMock()
    validador_ia.validar_proveedores = AsyncMock(return_value=[])

    buscador = BuscadorProveedores(
        cliente_busqueda=cliente_busqueda,
        validador_ia=validador_ia,
        logger=logging.getLogger("test_buscador"),
    )

    await buscador.buscar(
        profesion="capitan de barco",
        ciudad="cuenca",
        descripcion_problema="Necesito capitan de barco",
        domain="transporte",
        category="navegación marítima",
    )

    cliente_busqueda.buscar_proveedores.assert_awaited_once()
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["consulta"]
        == "capitan de barco transporte navegación marítima"
    )
    assert cliente_busqueda.buscar_proveedores.await_args.kwargs["limite"] == 15
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["descripcion_problema"]
        == "Necesito capitan de barco"
    )
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["domain"] == "transporte"
    )
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["category"]
        == "navegación marítima"
    )
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["search_profile"][
            "primary_service"
        ]
        == "capitan de barco"
    )
    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["search_profile"][
            "service_summary"
        ]
        == "capitan de barco"
    )
    search_profile = cliente_busqueda.buscar_proveedores.await_args.kwargs["search_profile"]
    assert search_profile["primary_service"] == "capitan de barco"
    assert search_profile["domain"] == "transporte"
    assert search_profile["category"] == "navegación marítima"
    validador_ia.validar_proveedores.assert_awaited_once()
    assert (
        validador_ia.validar_proveedores.await_args.kwargs["request_domain"]
        == "transporte"
    )
    assert (
        validador_ia.validar_proveedores.await_args.kwargs["request_category"]
        == "navegación marítima"
    )
    assert (
        validador_ia.validar_proveedores.await_args.kwargs["search_profile"][
            "primary_service"
        ]
        == "capitan de barco"
    )


@pytest.mark.asyncio
async def test_buscador_prefiere_service_summary_en_consulta(monkeypatch):
    cliente_busqueda = AsyncMock()
    cliente_busqueda.buscar_proveedores = AsyncMock(
        return_value={
            "ok": True,
            "providers": [],
            "total": 0,
            "search_metadata": {"strategy": "embeddings", "search_time_ms": 120},
        }
    )
    validador_ia = AsyncMock()
    validador_ia.validar_proveedores = AsyncMock(return_value=[])

    buscador = BuscadorProveedores(
        cliente_busqueda=cliente_busqueda,
        validador_ia=validador_ia,
        logger=logging.getLogger("test_buscador"),
    )

    await buscador.buscar(
        profesion="soporte y desarrollo de app móvil",
        ciudad="cuenca",
        descripcion_problema="Se presento un problema en la app movil y necesito soporte y desarrollo",
        domain="tecnología",
        category="desarrollo de software",
        search_profile={
            "primary_service": "soporte y desarrollo de app móvil",
            "service_summary": "Proveer soporte técnico y desarrollo para una aplicación móvil con problemas.",
            "domain": "tecnología",
            "category": "desarrollo de software",
        },
    )

    assert (
        cliente_busqueda.buscar_proveedores.await_args.kwargs["consulta"]
        == "Proveer soporte técnico y desarrollo para una aplicación móvil con problemas. tecnología desarrollo de software"
    )


@pytest.mark.asyncio
async def test_buscador_limita_validacion_a_candidatos_mas_relevantes(monkeypatch):
    monkeypatch.setattr(
        "services.buscador.buscador_proveedores.configuracion.search_validation_limit",
        2,
    )

    cliente_busqueda = AsyncMock()
    cliente_busqueda.buscar_proveedores = AsyncMock(
        return_value={
            "ok": True,
            "providers": [
                {
                    "id": "prov-1",
                    "first_name": "Proveedor",
                    "last_name": "Uno",
                    "services": ["desarrollo de software"],
                    "semantic_alignment_score": 0.91,
                    "retrieval_score": 0.83,
                    "similarity_score": 0.80,
                    "classification_confidence": 1.0,
                    "rating": 4.8,
                    "verified": True,
                },
                {
                    "id": "prov-2",
                    "first_name": "Proveedor",
                    "last_name": "Dos",
                    "services": ["renta de departamentos"],
                    "semantic_alignment_score": 0.12,
                    "retrieval_score": 0.79,
                    "similarity_score": 0.76,
                    "classification_confidence": 1.0,
                    "rating": 5.0,
                    "verified": True,
                },
                {
                    "id": "prov-3",
                    "first_name": "Proveedor",
                    "last_name": "Tres",
                    "services": ["asesoría en tecnología de la información"],
                    "semantic_alignment_score": 0.74,
                    "retrieval_score": 0.81,
                    "similarity_score": 0.78,
                    "classification_confidence": 1.0,
                    "rating": 4.9,
                    "verified": True,
                },
            ],
            "total": 3,
            "search_metadata": {"strategy": "embeddings", "search_time_ms": 250},
        }
    )
    validador_ia = AsyncMock()
    validador_ia.validar_proveedores = AsyncMock(return_value=[])

    buscador = BuscadorProveedores(
        cliente_busqueda=cliente_busqueda,
        validador_ia=validador_ia,
        logger=logging.getLogger("test_buscador"),
    )

    await buscador.buscar(
        profesion="desarrollo de aplicación móvil",
        ciudad="cuenca",
        descripcion_problema="Necesito construir una aplicación móvil",
        domain="tecnología",
        category="desarrollo de software",
    )

    proveedores_enviados = validador_ia.validar_proveedores.await_args.kwargs[
        "proveedores"
    ]
    assert len(proveedores_enviados) == 2
    assert [p["id"] for p in proveedores_enviados] == ["prov-1", "prov-3"]
