from types import SimpleNamespace

import pytest

from services.taxonomia.sugerencias import enriquecer_sugerencia_taxonomia


class _SupabaseQueryStub:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _SupabaseStub:
    def __init__(self, provider_services):
        self._provider_services = provider_services

    def table(self, table_name: str):
        assert table_name == "provider_services"
        return _SupabaseQueryStub(self._provider_services)


@pytest.mark.asyncio
async def test_enriquecer_sugerencia_propone_new_canonical_si_match_provider_service(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.sugerencias.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

    propuesta = await enriquecer_sugerencia_taxonomia(
        supabase=_SupabaseStub(
            [{"service_name": "revisión mecánica para compra de auto"}]
        ),
        normalized_text="revision mecanica para compra de auto",
        taxonomia={"domains": []},
        proposed_domain_code="vehiculos",
    )

    assert propuesta["proposal_type"] == "new_canonical"
    assert propuesta["proposed_domain_code"] == "vehiculos"
    assert "revisión mecánica para compra de auto" in propuesta["proposed_canonical_name"]


@pytest.mark.asyncio
async def test_enriquecer_sugerencia_reusa_canonico_existente(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.sugerencias.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

    propuesta = await enriquecer_sugerencia_taxonomia(
        supabase=_SupabaseStub([]),
        normalized_text="revision mecanica para compra de auto",
        taxonomia={
            "domains": [
                {
                    "code": "vehiculos",
                    "aliases": [],
                    "canonical_services": [
                        {
                            "canonical_name": "revisión mecánica para compra de auto",
                            "canonical_normalized": "revision mecanica para compra de auto",
                        }
                    ],
                }
            ]
        },
        proposed_domain_code="vehiculos",
    )

    assert propuesta["proposal_type"] == "alias"
    assert propuesta["proposed_domain_code"] == "vehiculos"
    assert propuesta["proposed_canonical_name"] == "revisión mecánica para compra de auto"
