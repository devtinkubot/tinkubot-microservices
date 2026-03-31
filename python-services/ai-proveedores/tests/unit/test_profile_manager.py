from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import pytest

imghdr_stub: Any = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.session.profile_manager import (  # noqa: E402
    _normalizar_real_phone_para_busqueda,
    obtener_perfil_proveedor,
)


class _QueryStub:
    def __init__(self, table_name: str, fixtures: Dict[str, Dict[str, List[Dict[str, Any]]]]):
        self.table_name = table_name
        self.fixtures = fixtures
        self.filters: List[tuple[str, Any]] = []
        self.limit_value: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: Any):
        self.filters.append((field, value))
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def execute(self):
        table_fixtures = self.fixtures.get(self.table_name, {})
        data: List[Dict[str, Any]] = []
        if self.filters:
            field, value = self.filters[-1]
            data = list(table_fixtures.get(f"{field}={value}", []))
        if self.limit_value is not None:
            data = data[: self.limit_value]
        return types.SimpleNamespace(data=data)


class _SupabaseStub:
    def __init__(self, fixtures: Dict[str, Dict[str, List[Dict[str, Any]]]]):
        self.fixtures = fixtures

    def table(self, table_name: str):
        return _QueryStub(table_name, self.fixtures)


@pytest.mark.asyncio
async def test_obtener_perfil_proveedor_prefiere_aprobado_por_real_phone_sobre_pending(
    monkeypatch,
):
    fixtures = {
        "providers": {
            "id=prov-pending": [
                {
                    "id": "prov-pending",
                    "phone": "593992846648@s.whatsapp.net",
                    "real_phone": "593992846648",
                    "status": "pending",
                    "verified": True,
                    "has_consent": True,
                    "full_name": "",
                    "services": [],
                }
            ],
            "phone=593992846648@s.whatsapp.net": [
                {
                    "id": "prov-pending",
                    "phone": "593992846648@s.whatsapp.net",
                    "real_phone": "593992846648",
                    "status": "pending",
                    "verified": True,
                    "has_consent": True,
                    "full_name": "",
                    "services": [],
                }
            ],
            "real_phone=593992846648": [
                {
                    "id": "prov-approved",
                    "phone": "102550967742602@lid",
                    "real_phone": "593992846648",
                    "status": "approved",
                    "verified": True,
                    "has_consent": True,
                    "full_name": "Mariuxi Norma Rivas Tapia",
                    "services": [],
                }
            ],
        }
    }
    supabase = _SupabaseStub(fixtures)

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    async def _fake_resolver_provider_id_por_identidad(*_args, **_kwargs):
        return "prov-pending"

    async def _fake_servicios_relacionados(**_kwargs):
        return []

    monkeypatch.setattr(
        "flows.session.profile_manager.run_supabase", _fake_run_supabase
    )
    monkeypatch.setattr(
        "flows.session.profile_manager.resolver_provider_id_por_identidad",
        _fake_resolver_provider_id_por_identidad,
    )
    monkeypatch.setattr(
        "flows.session.profile_manager._obtener_servicios_relacionados",
        _fake_servicios_relacionados,
    )
    monkeypatch.setattr(
        "infrastructure.database.get_supabase_client",
        lambda: supabase,
    )

    perfil = await obtener_perfil_proveedor(
        "593992846648@s.whatsapp.net",
        account_id="bot-proveedores",
    )

    assert perfil is not None
    assert perfil["id"] == "prov-approved"
    assert perfil["status"] == "approved"
    assert perfil["_match_source"] == "real_phone"


def test_normalizar_real_phone_para_busqueda_solo_resuelve_numericos_usables():
    assert _normalizar_real_phone_para_busqueda("593992846648@s.whatsapp.net") == (
        "593992846648"
    )
    assert _normalizar_real_phone_para_busqueda("US.13491208655302741918@lid") is None
    assert _normalizar_real_phone_para_busqueda("Mariuxi Rivas") is None

