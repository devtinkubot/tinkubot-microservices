from types import SimpleNamespace

import pytest

from services.taxonomia.catalogo_publicado import (
    construir_mensaje_precision_cliente,
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
    def __init__(self, values=None):
        self.values = values or {}
        self.saved = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, expire=None):
        self.values[key] = value
        self.saved.append((key, value, expire))


@pytest.mark.asyncio
async def test_obtener_taxonomia_publicada_arma_payload_y_guarda_cache(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
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
    redis_client = _RedisStub()

    payload = await obtener_taxonomia_publicada(supabase, redis_client=redis_client)

    assert payload["version"] == 1
    assert payload["domains"][0]["code"] == "legal"
    assert payload["domains"][0]["aliases"][0]["alias_normalized"] == "abogado"
    assert payload["domains"][0]["canonical_services"][0]["canonical_name"] == "abogado laboral"
    assert payload["domains"][0]["precision_rule"]["id"] == "rule-1"
    assert redis_client.values["service-taxonomy:version"] == 1
    assert redis_client.values["service-taxonomy:domains"] == payload


@pytest.mark.asyncio
async def test_obtener_taxonomia_publicada_usa_cache_si_esta_completo(monkeypatch):
    async def _unexpected_run_supabase(*_args, **_kwargs):
        raise AssertionError("no debe consultar supabase")

    monkeypatch.setattr(
        "services.taxonomia.catalogo_publicado.run_supabase",
        _unexpected_run_supabase,
    )

    payload_cache = {
        "version": 3,
        "publication": {"version": 3, "status": "published"},
        "domains": [{"id": "dom-1", "code": "tecnologia"}],
    }
    redis_client = _RedisStub(
        {
            "service-taxonomy:version": 3,
            "service-taxonomy:domains": payload_cache,
        }
    )

    payload = await obtener_taxonomia_publicada(object(), redis_client=redis_client)

    assert payload == payload_cache


@pytest.mark.asyncio
async def test_obtener_taxonomia_publicada_retorna_none_si_no_hay_publicacion(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.catalogo_publicado.run_supabase",
        _fake_run_supabase,
    )

    supabase = _SupabaseStub(
        {
            "service_taxonomy_publications": [],
            "service_domains": [],
            "service_domain_aliases": [],
            "service_canonical_services": [],
            "service_precision_rules": [],
        }
    )

    payload = await obtener_taxonomia_publicada(supabase, redis_client=None)

    assert payload is None


def test_construir_mensaje_precision_cliente_desde_regla_publicada():
    taxonomia = {
        "version": 1,
        "publication": {"version": 1, "status": "published"},
        "domains": [
            {
                "id": "dom-1",
                "code": "inmobiliario",
                "aliases": [
                    {"alias_normalized": "servicio inmobiliario", "is_active": True}
                ],
                "precision_rule": {
                    "client_prompt_template": "Indica si buscas comprar, vender o rentar y qué tipo de inmueble.",
                    "required_dimensions": ["operacion", "tipo de inmueble"],
                    "generic_examples": ["asesoria inmobiliaria"],
                    "sufficient_examples": ["compra de casa", "renta de departamento"],
                },
            }
        ],
    }

    mensaje = construir_mensaje_precision_cliente(
        "servicio inmobiliario",
        taxonomia,
    )

    assert "Indica si buscas comprar, vender o rentar" in mensaje
    assert "operacion" in mensaje
    assert "tipo de inmueble" in mensaje
    assert "compra de casa" in mensaje


def test_resolver_servicio_canonico_publicado_retorna_canonico_por_alias():
    taxonomia = {
        "version": 1,
        "publication": {"version": 1, "status": "published"},
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
                "precision_rule": None,
            }
        ],
    }

    assert (
        resolver_servicio_canonico_publicado("laboralista", taxonomia)
        == "abogado laboral"
    )
