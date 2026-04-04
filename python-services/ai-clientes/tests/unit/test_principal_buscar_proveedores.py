"""Regresiones para el wrapper público de búsqueda en principal."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import principal


@pytest.mark.asyncio
async def test_buscar_proveedores_propagates_search_profile(monkeypatch):
    buscador = AsyncMock()
    buscador.buscar = AsyncMock(
        return_value={"ok": True, "providers": [], "total": 0}
    )
    monkeypatch.setattr(principal, "orquestador", SimpleNamespace(buscador=buscador))

    search_profile = {
        "raw_input": "El jardin está decuidado y los arboles por podar, necesito ayuda",
        "primary_service": "poda de jardines",
        "domain": "jardinería",
        "category": "mantenimiento de jardines",
        "signals": ["servicio objetivo: poda de jardines"],
        "confidence": 0.8,
        "source": "client",
    }

    resultado = await principal.buscar_proveedores(
        servicio="poda de jardines",
        ciudad="Cuenca",
        descripcion_problema="El jardin está decuidado y los arboles por podar, necesito ayuda",
        domain="jardinería",
        category="mantenimiento de jardines",
        search_profile=search_profile,
    )

    assert resultado["ok"] is True
    buscador.buscar.assert_awaited_once()
    assert buscador.buscar.await_args.kwargs["search_profile"] == search_profile
    assert buscador.buscar.await_args.kwargs["domain"] == "jardinería"
    assert buscador.buscar.await_args.kwargs["category"] == "mantenimiento de jardines"
