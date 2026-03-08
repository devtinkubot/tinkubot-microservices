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
                    "full_name": "Proveedor Uno",
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
    )

    cliente_busqueda.buscar_proveedores.assert_awaited_once()
    assert cliente_busqueda.buscar_proveedores.await_args.kwargs["limite"] == 15
    validador_ia.validar_proveedores.assert_awaited_once()
