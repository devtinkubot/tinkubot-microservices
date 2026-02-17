"""Contract tests for IRepositorioClientes implementations."""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from contracts.repositorios import IRepositorioClientes
from infrastructure.persistencia.repositorio_clientes import RepositorioClientesSupabase


@dataclass
class _Resp:
    data: Any


class _FakeQuery:
    def __init__(self, db: "_FakeSupabase", table_name: str) -> None:
        self.db = db
        self.table_name = table_name
        self.op: Optional[str] = None
        self.payload: Optional[Dict[str, Any]] = None
        self.filters: Dict[str, Any] = {}

    def select(self, _fields: str):
        self.op = "select"
        return self

    def insert(self, payload: Dict[str, Any]):
        self.op = "insert"
        self.payload = payload
        return self

    def update(self, payload: Dict[str, Any]):
        self.op = "update"
        self.payload = payload
        return self

    def eq(self, field: str, value: Any):
        self.filters[field] = value
        return self

    def limit(self, _n: int):
        return self

    def execute(self):
        if self.table_name == "customers":
            return self._execute_customers()
        if self.table_name == "consents":
            return self._execute_consents()
        return _Resp(data=[])

    def _execute_customers(self):
        if self.op == "select":
            if "phone_number" in self.filters:
                phone = self.filters["phone_number"]
                customer = self.db.customers_by_phone.get(phone)
                return _Resp(data=[customer] if customer else [])
            if "id" in self.filters:
                cid = self.filters["id"]
                for customer in self.db.customers_by_phone.values():
                    if customer["id"] == cid:
                        return _Resp(data=[customer])
                return _Resp(data=[])
            return _Resp(data=[])

        if self.op == "insert":
            payload = dict(self.payload or {})
            if self.table_name == "customers":
                cid = f"cust-{self.db.seq}"
                self.db.seq += 1
                created = {
                    "id": cid,
                    "phone_number": payload.get("phone_number"),
                    "full_name": payload.get("full_name"),
                    "city": payload.get("city"),
                    "city_confirmed_at": payload.get("city_confirmed_at"),
                    "has_consent": False,
                    "notes": None,
                    "created_at": None,
                    "updated_at": None,
                }
                self.db.customers_by_phone[created["phone_number"]] = created
                return _Resp(data=[created])

        if self.op == "update":
            cid = self.filters.get("id")
            if not cid:
                return _Resp(data=[])
            for customer in self.db.customers_by_phone.values():
                if customer["id"] == cid:
                    customer.update(self.payload or {})
                    return _Resp(data=[customer])
            return _Resp(data=[])

        return _Resp(data=[])

    def _execute_consents(self):
        if self.op == "insert":
            self.db.consents.append(dict(self.payload or {}))
            return _Resp(data=[self.db.consents[-1]])
        return _Resp(data=[])


class _FakeSupabase:
    def __init__(self) -> None:
        self.customers_by_phone: Dict[str, Dict[str, Any]] = {}
        self.consents = []
        self.seq = 1

    def table(self, table_name: str):
        return _FakeQuery(self, table_name)


@pytest.fixture
def repo(monkeypatch) -> RepositorioClientesSupabase:
    async def _fake_run_supabase(fn, etiqueta=None, timeout=None):
        return fn()

    monkeypatch.setattr(
        "infrastructure.persistencia.repositorio_clientes.run_supabase",
        _fake_run_supabase,
    )
    return RepositorioClientesSupabase(_FakeSupabase())


@pytest.mark.asyncio
async def test_repositorio_clientes_cumple_contrato(repo: RepositorioClientesSupabase):
    assert isinstance(repo, IRepositorioClientes)


@pytest.mark.asyncio
async def test_contrato_obtener_o_crear_y_actualizar(repo: RepositorioClientesSupabase):
    created = await repo.obtener_o_crear(
        telefono="593990000010", nombre_completo="Cliente Prueba", ciudad="Cuenca"
    )
    assert created is not None
    assert created["phone_number"] == "593990000010"
    assert created["city"] == "Cuenca"

    updated_city = await repo.actualizar_ciudad(created["id"], "Quito")
    assert updated_city is not None
    assert updated_city["city"] == "Quito"

    updated_consent = await repo.actualizar_consentimiento(created["id"], True)
    assert updated_consent is not None
    assert updated_consent["has_consent"] is True


@pytest.mark.asyncio
async def test_contrato_limpieza_y_registro_consentimiento(repo: RepositorioClientesSupabase):
    created = await repo.obtener_o_crear(
        telefono="593990000011", nombre_completo="Cliente Dos", ciudad="Loja"
    )
    assert created is not None

    await repo.limpiar_ciudad(created["id"])
    await repo.limpiar_consentimiento(created["id"])
    await asyncio.sleep(0)

    refreshed = await repo.actualizar_consentimiento(created["id"], False)
    assert refreshed is not None
    assert refreshed["city"] is None
    assert refreshed["city_confirmed_at"] is None
    assert refreshed["has_consent"] is False

    ok = await repo.registrar_consentimiento(
        usuario_id=created["id"],
        respuesta="accepted",
        datos_consentimiento={"source": "contract-test"},
    )
    assert ok is True
