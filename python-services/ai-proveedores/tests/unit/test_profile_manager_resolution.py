from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

imghdr_stub: Any = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.session.profile_manager import obtener_perfil_proveedor  # noqa: E402


class _QueryStub:
    def __init__(self, supabase: "_SupabaseStub", table: str):
        self._supabase = supabase
        self._table = table
        self._eq: Dict[str, str] = {}
        self._limit: Optional[int] = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col: str, value: Any):
        self._eq[str(col)] = str(value)
        return self

    def in_(self, col: str, values: Any):
        # Not needed for these tests.
        self._eq[str(col)] = ",".join(str(v) for v in (values or []))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def execute(self):
        data: List[Dict[str, Any]] = []

        if self._table == "providers":
            if "id" in self._eq:
                row = self._supabase.providers_by_id.get(self._eq["id"])
                data = [row] if row else []
            elif "phone" in self._eq:
                row = self._supabase.providers_by_phone.get(self._eq["phone"])
                data = [row] if row else []
            elif "real_phone" in self._eq:
                key = self._eq["real_phone"]
                if self._supabase.raise_on_real_phone_lookup:
                    raise RuntimeError("real_phone lookup not expected")
                data = list(self._supabase.providers_by_real_phone.get(key) or [])
        elif self._table == "provider_services":
            pid = self._eq.get("provider_id") or ""
            data = list(self._supabase.provider_services_by_provider.get(pid) or [])

        if self._limit is not None:
            data = data[: self._limit]

        return types.SimpleNamespace(data=data)


class _SupabaseStub:
    def __init__(
        self,
        *,
        providers_by_id: Dict[str, Dict[str, Any]] | None = None,
        providers_by_phone: Dict[str, Dict[str, Any]] | None = None,
        providers_by_real_phone: Dict[str, List[Dict[str, Any]]] | None = None,
        provider_services_by_provider: Dict[str, List[Dict[str, Any]]] | None = None,
        raise_on_real_phone_lookup: bool = False,
    ):
        self.providers_by_id = providers_by_id or {}
        self.providers_by_phone = providers_by_phone or {}
        self.providers_by_real_phone = providers_by_real_phone or {}
        self.provider_services_by_provider = provider_services_by_provider or {}
        self.raise_on_real_phone_lookup = raise_on_real_phone_lookup

    def table(self, table_name: str):
        return _QueryStub(self, table_name)


@pytest.mark.asyncio
async def test_inbound_numerico_prefiere_aprobado_por_real_phone_sobre_pending_por_phone(
    monkeypatch,
):
    telefono = "593992846648@s.whatsapp.net"

    pending = {
        "id": "prov-pending",
        "phone": telefono,
        "real_phone": "593992846648",
        "status": "pending",
        "verified": True,
        "has_consent": True,
    }
    approved = {
        "id": "prov-approved",
        "phone": "102550967742602@lid",
        "real_phone": "593992846648",
        "status": "approved",
        "verified": True,
        "has_consent": True,
        "approved_notified_at": "2026-02-20T21:48:25Z",
    }

    supabase = _SupabaseStub(
        providers_by_phone={telefono: pending},
        providers_by_real_phone={"593992846648": [approved, pending]},
    )

    async def _fake_run_supabase(op, **_kwargs):
        return op()

    async def _fake_resolver_provider_id_por_identidad(*_args, **_kwargs):
        return None

    monkeypatch.setattr("infrastructure.database.get_supabase_client", lambda: supabase)
    monkeypatch.setattr("flows.session.profile_manager.run_supabase", _fake_run_supabase)
    monkeypatch.setattr(
        "flows.session.profile_manager.resolver_provider_id_por_identidad",
        _fake_resolver_provider_id_por_identidad,
    )
    monkeypatch.setattr(
        "flows.session.profile_manager.garantizar_campos_obligatorios_proveedor",
        lambda x: x,
    )
    monkeypatch.setattr(
        "flows.session.profile_manager.extraer_servicios_guardados",
        lambda _x: [],
    )

    perfil = await obtener_perfil_proveedor(telefono, account_id="bot-proveedores")
    assert perfil is not None
    assert perfil["id"] == "prov-approved"


@pytest.mark.asyncio
async def test_inbound_lid_no_hace_lookup_por_real_phone(monkeypatch):
    telefono = "US.1234567890@lid"
    supabase = _SupabaseStub(raise_on_real_phone_lookup=True)

    async def _fake_run_supabase(op, **_kwargs):
        return op()

    async def _fake_resolver_provider_id_por_identidad(*_args, **_kwargs):
        return None

    monkeypatch.setattr("infrastructure.database.get_supabase_client", lambda: supabase)
    monkeypatch.setattr("flows.session.profile_manager.run_supabase", _fake_run_supabase)
    monkeypatch.setattr(
        "flows.session.profile_manager.resolver_provider_id_por_identidad",
        _fake_resolver_provider_id_por_identidad,
    )
    monkeypatch.setattr(
        "flows.session.profile_manager.garantizar_campos_obligatorios_proveedor",
        lambda x: x,
    )
    monkeypatch.setattr(
        "flows.session.profile_manager.extraer_servicios_guardados",
        lambda _x: [],
    )

    perfil = await obtener_perfil_proveedor(telefono, account_id="bot-proveedores")
    assert perfil is None
