import asyncio
from types import SimpleNamespace

from services.taxonomia import lector_taxonomia_publicada as modulo_lector

LectorTaxonomiaPublicada = modulo_lector.LectorTaxonomiaPublicada


class _FakeClock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        return self._now

    def avanzar(self, segundos: float) -> None:
        self._now += segundos


class _FakeQuery:
    def __init__(self, supabase, table_name):
        self._supabase = supabase
        self._table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        self._supabase.calls.append(self._table_name)
        data = self._supabase.responses.get(self._table_name, [])
        return SimpleNamespace(data=data)


class _FakeSupabase:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def table(self, table_name):
        return _FakeQuery(self, table_name)


async def _run_supabase_directo(op, timeout=None, label=None):
    del timeout, label
    return op()


def _parchar_run_supabase():
    modulo_lector.run_supabase = _run_supabase_directo


def test_lector_construye_taxonomia_publicada():
    _parchar_run_supabase()
    supabase = _FakeSupabase(
        {
            "service_taxonomy_publications": [
                {
                    "id": "pub-1",
                    "version": "v1",
                    "status": "active",
                    "published_by": "admin",
                    "published_at": "2026-03-10T00:00:00Z",
                    "notes": "base",
                }
            ],
            "service_domains": [
                {
                    "id": "dom-legal",
                    "code": "legal",
                    "display_name": "Legal",
                    "status": "active",
                    "description": "Servicios legales",
                    "is_critical": True,
                },
                {
                    "id": "dom-tech",
                    "code": "tecnologia",
                    "display_name": "Tecnologia",
                    "status": "active",
                    "description": "Servicios de tecnologia",
                    "is_critical": False,
                },
            ],
            "service_domain_aliases": [
                {
                    "id": "alias-1",
                    "domain_id": "dom-legal",
                    "alias_text": "abogado",
                    "alias_normalized": "abogado",
                    "priority": 1,
                    "status": "active",
                }
            ],
            "service_canonical_services": [
                {
                    "id": "canon-1",
                    "domain_id": "dom-legal",
                    "canonical_name": "abogado laboral",
                    "canonical_normalized": "abogado laboral",
                    "description": "Laboral",
                    "metadata_json": {},
                    "status": "active",
                }
            ],
            "service_precision_rules": [
                {
                    "id": "rule-1",
                    "domain_id": "dom-legal",
                    "required_dimensions": ["area"],
                    "generic_examples": ["asesoria legal"],
                    "sufficient_examples": ["defensa laboral"],
                    "client_prompt_template": "cliente",
                    "provider_prompt_template": "proveedor",
                }
            ],
        }
    )

    lector = LectorTaxonomiaPublicada(supabase=supabase, ttl_segundos=60)

    taxonomia = asyncio.run(lector.obtener_taxonomia_publicada())

    assert taxonomia["version"] == "v1"
    assert taxonomia["publication"]["id"] == "pub-1"
    assert [dominio["code"] for dominio in taxonomia["domains"]] == [
        "legal",
        "tecnologia",
    ]
    assert taxonomia["domains"][0]["aliases"][0]["alias_normalized"] == "abogado"
    assert taxonomia["domains"][0]["canonical_services"][0]["canonical_name"] == "abogado laboral"
    assert taxonomia["domains"][0]["rules"][0]["required_dimensions"] == ["area"]
    assert taxonomia["domains"][1]["canonical_services"] == []
    assert taxonomia["domains"][1]["aliases"] == []
    assert taxonomia["domains"][1]["rules"] == []


def test_lector_reutiliza_cache_dentro_del_ttl():
    _parchar_run_supabase()
    clock = _FakeClock()
    supabase = _FakeSupabase(
        {
            "service_taxonomy_publications": [
                {
                    "id": "pub-1",
                    "version": "v1",
                    "status": "active",
                    "published_by": "admin",
                    "published_at": "2026-03-10T00:00:00Z",
                    "notes": None,
                }
            ],
            "service_domains": [],
            "service_domain_aliases": [],
            "service_canonical_services": [],
            "service_precision_rules": [],
        }
    )
    lector = LectorTaxonomiaPublicada(
        supabase=supabase,
        ttl_segundos=30,
        clock=clock,
    )

    primera = asyncio.run(lector.obtener_taxonomia_publicada())
    segunda = asyncio.run(lector.obtener_taxonomia_publicada())

    assert primera["version"] == "v1"
    assert segunda["version"] == "v1"
    assert supabase.calls.count("service_taxonomy_publications") == 1
    assert supabase.calls.count("service_domains") == 1


def test_lector_refresca_cache_cuando_expira_o_se_fuerza():
    _parchar_run_supabase()
    clock = _FakeClock()
    supabase = _FakeSupabase(
        {
            "service_taxonomy_publications": [
                {
                    "id": "pub-1",
                    "version": "v1",
                    "status": "active",
                    "published_by": "admin",
                    "published_at": "2026-03-10T00:00:00Z",
                    "notes": None,
                }
            ],
            "service_domains": [],
            "service_domain_aliases": [],
            "service_canonical_services": [],
            "service_precision_rules": [],
        }
    )
    lector = LectorTaxonomiaPublicada(
        supabase=supabase,
        ttl_segundos=10,
        clock=clock,
    )

    asyncio.run(lector.obtener_taxonomia_publicada())

    supabase.responses["service_taxonomy_publications"] = [
        {
            "id": "pub-2",
            "version": "v2",
            "status": "active",
            "published_by": "admin",
            "published_at": "2026-03-11T00:00:00Z",
            "notes": None,
        }
    ]

    clock.avanzar(11)
    expirada = asyncio.run(lector.obtener_taxonomia_publicada())
    forzada = asyncio.run(lector.obtener_taxonomia_publicada(force_refresh=True))

    assert expirada["version"] == "v2"
    assert forzada["version"] == "v2"
    assert supabase.calls.count("service_taxonomy_publications") == 3


def test_lector_devuelve_vacio_seguro_si_no_hay_publicacion_activa():
    _parchar_run_supabase()
    supabase = _FakeSupabase(
        {
            "service_taxonomy_publications": [],
        }
    )
    lector = LectorTaxonomiaPublicada(supabase=supabase, ttl_segundos=60)

    taxonomia = asyncio.run(lector.obtener_taxonomia_publicada())

    assert taxonomia == {
        "publication": None,
        "version": None,
        "domains": [],
    }
    assert supabase.calls == ["service_taxonomy_publications"]


def test_lector_acepta_registros_publicados_reales():
    supabase = _FakeSupabase(
        {
            "service_taxonomy_publications": [
                {
                    "id": "pub-1",
                    "version": 1,
                    "status": "published",
                    "published_by": "system_seed",
                    "published_at": "2026-03-10T00:00:00Z",
                    "notes": "seed",
                }
            ],
            "service_domains": [
                {
                    "id": "dom-legal",
                    "code": "legal",
                    "display_name": "Legal",
                    "status": "published",
                    "description": "Servicios legales",
                    "is_critical": True,
                }
            ],
            "service_domain_aliases": [
                {
                    "id": "alias-1",
                    "domain_id": "dom-legal",
                    "alias_text": "abogado",
                    "alias_normalized": "abogado",
                    "priority": 1,
                    "is_active": True,
                }
            ],
            "service_canonical_services": [
                {
                    "id": "canon-1",
                    "domain_id": "dom-legal",
                    "canonical_name": "abogado laboral",
                    "canonical_normalized": "abogado laboral",
                    "description": "Laboral",
                    "metadata_json": {},
                    "status": "active",
                }
            ],
            "service_precision_rules": [
                {
                    "id": "rule-1",
                    "domain_id": "dom-legal",
                    "generic_examples": ["asesoria legal"],
                }
            ],
        }
    )
    lector = LectorTaxonomiaPublicada(supabase=supabase, ttl_segundos=60)

    taxonomia = asyncio.run(lector.obtener_taxonomia_publicada())

    assert taxonomia["version"] == 1
    assert taxonomia["domains"][0]["status"] == "published"
    assert taxonomia["domains"][0]["aliases"][0]["alias_normalized"] == "abogado"
    assert taxonomia["domains"][0]["canonical_services"][0]["canonical_name"] == "abogado laboral"
