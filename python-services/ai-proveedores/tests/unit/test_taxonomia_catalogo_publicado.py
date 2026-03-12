from types import SimpleNamespace

import pytest

from services.taxonomia.catalogo_publicado import (
    obtener_taxonomia_publicada,
    resolver_servicio_canonico_publicado,
)


class _SupabaseQueryStub:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _SupabaseStub:
    def __init__(self, tables):
        self._tables = tables

    def table(self, table_name: str):
        return _SupabaseQueryStub(self._tables[table_name])


class _RedisStub:
    def __init__(self, values=None, fail=False):
        self.values = values or {}
        self.fail = fail

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        return self.values.get(key)

    async def set(self, key, value, expire=None):
        if self.fail:
            raise RuntimeError("redis down")
        self.values[key] = value


@pytest.mark.asyncio
async def test_obtener_taxonomia_publicada_arma_payload_y_degrada_cache(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.catalogo_publicado.run_supabase",
        _fake_run_supabase,
    )

    supabase = _SupabaseStub(
        {
            "service_taxonomy_publications": [{"version": 1, "status": "published"}],
            "service_domains": [{"id": "dom-1", "code": "legal", "status": "published"}],
            "service_domain_aliases": [
                {
                    "id": "alias-1",
                    "domain_id": "dom-1",
                    "alias_normalized": "abogado",
                    "is_active": True,
                }
            ],
            "service_canonical_services": [
                {
                    "id": "canon-1",
                    "domain_id": "dom-1",
                    "canonical_name": "abogado laboral",
                    "canonical_normalized": "abogado laboral",
                    "status": "active",
                }
            ],
            "service_precision_rules": [{"id": "rule-1", "domain_id": "dom-1"}],
        }
    )

    payload = await obtener_taxonomia_publicada(
        supabase,
        redis_client=_RedisStub(fail=True),
    )

    assert payload["version"] == 1
    assert payload["domains"][0]["aliases"][0]["alias_normalized"] == "abogado"
    assert payload["domains"][0]["canonical_services"][0]["canonical_name"] == "abogado laboral"


@pytest.mark.asyncio
async def test_obtener_taxonomia_publicada_usa_cache_si_esta_completo(monkeypatch):
    async def _unexpected_run_supabase(*_args, **_kwargs):
        raise AssertionError("no debe consultar supabase")

    monkeypatch.setattr(
        "services.taxonomia.catalogo_publicado.run_supabase",
        _unexpected_run_supabase,
    )

    payload_cache = {
        "version": 2,
        "publication": {"version": 2, "status": "published"},
        "domains": [{"id": "dom-1", "code": "transporte", "canonical_services": []}],
    }
    redis_client = _RedisStub(
        {
            "service-taxonomy:version": 2,
            "service-taxonomy:domains": payload_cache,
        }
    )

    payload = await obtener_taxonomia_publicada(object(), redis_client=redis_client)

    assert payload == payload_cache


def test_resolver_servicio_canonico_publicado_retorna_canonico_por_alias():
    taxonomia = {
        "version": 2,
        "publication": {"version": 2, "status": "published"},
        "domains": [
            {
                "id": "dom-1",
                "code": "legal",
                "aliases": [
                    {
                        "alias_text": "laboralista",
                        "alias_normalized": "laboralista",
                        "canonical_service_id": "canon-1",
                    }
                ],
                "canonical_services": [
                    {
                        "id": "canon-1",
                        "canonical_name": "abogado laboral",
                        "canonical_normalized": "abogado laboral",
                    }
                ],
                "rules": [],
            }
        ],
    }

    assert (
        resolver_servicio_canonico_publicado("laboralista", taxonomia)
        == "abogado laboral"
    )
