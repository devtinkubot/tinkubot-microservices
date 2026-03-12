from types import SimpleNamespace

import pytest

from services.taxonomia.sugerencias import (
    encontrar_mejor_alias,
    encontrar_mejor_canonico,
    enriquecer_sugerencia_taxonomia,
)


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
async def test_enriquecer_sugerencia_propone_alias_si_coincide_con_taxonomia(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.sugerencias.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

    taxonomia = {
        "domains": [
            {
                "code": "legal",
                "aliases": [
                    {
                        "alias_text": "asesoría legal",
                        "alias_normalized": "asesoria legal",
                    }
                ],
            }
        ]
    }

    propuesta = await enriquecer_sugerencia_taxonomia(
        supabase=_SupabaseStub([]),
        normalized_text="asesoria legal",
        taxonomia=taxonomia,
    )

    assert propuesta["proposal_type"] == "alias"
    assert propuesta["proposed_domain_code"] == "legal"


def test_encontrar_mejor_alias_retorna_mejor_match():
    taxonomia = {
        "domains": [
            {
                "code": "inmobiliario",
                "aliases": [
                    {
                        "alias_text": "asesoría inmobiliaria",
                        "alias_normalized": "asesoria inmobiliaria",
                    }
                ],
            }
        ]
    }

    match = encontrar_mejor_alias("asesoria inmobiliaria", taxonomia)

    assert match is not None
    assert match["domain_code"] == "inmobiliario"
    assert match["similarity"] == 1.0


def test_encontrar_mejor_canonico_retorna_match_canonico():
    taxonomia = {
        "domains": [
            {
                "code": "vehiculos",
                "canonical_services": [
                    {
                        "canonical_name": "revisión mecánica para compra de auto",
                        "canonical_normalized": "revision mecanica para compra de auto",
                    }
                ],
            }
        ]
    }

    match = encontrar_mejor_canonico("revision mecanica para compra de auto", taxonomia)

    assert match is not None
    assert match["domain_code"] == "vehiculos"
    assert match["canonical_name"] == "revisión mecánica para compra de auto"
    assert match["similarity"] == 1.0


@pytest.mark.asyncio
async def test_enriquecer_sugerencia_reusa_canonico_existente(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.sugerencias.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

    taxonomia = {
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
    }

    propuesta = await enriquecer_sugerencia_taxonomia(
        supabase=_SupabaseStub([]),
        normalized_text="revision mecanica para compra de auto",
        taxonomia=taxonomia,
    )

    assert propuesta["proposal_type"] == "alias"
    assert propuesta["proposed_domain_code"] == "vehiculos"
    assert propuesta["proposed_canonical_name"] == "revisión mecánica para compra de auto"
