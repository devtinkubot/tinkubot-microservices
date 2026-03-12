from types import SimpleNamespace

import pytest

from services.taxonomia.clasificador import clasificar_servicio_taxonomia


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
async def test_clasificar_servicio_taxonomia_retorna_contrato_insufficient(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

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
                "rules": [
                    {
                        "required_dimensions": ["materia", "tramite"],
                        "provider_prompt_template": "Describe el área legal y el trámite exacto.",
                        "sufficient_examples": ["defensa en demanda laboral"],
                    }
                ],
            }
        ]
    }

    clasificacion = await clasificar_servicio_taxonomia(
        supabase=_SupabaseStub([]),
        servicio="asesoria legal",
        taxonomia=taxonomia,
        audience="provider",
    )

    assert clasificacion["domain"] == "legal"
    assert clasificacion["specificity"] == "insufficient"
    assert clasificacion["missing_dimensions"] == ["materia", "tramite"]
    assert "área legal" in clasificacion["clarification_question"]


@pytest.mark.asyncio
async def test_clasificar_servicio_taxonomia_retorna_contrato_new_canonical(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, label=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

    clasificacion = await clasificar_servicio_taxonomia(
        supabase=_SupabaseStub([{"service_name": "revisión mecánica para compra de auto"}]),
        servicio="revision mecanica para compra de auto",
        taxonomia={"domains": []},
        audience="provider",
        proposed_domain_code="vehiculos",
    )

    assert clasificacion["domain"] == "vehiculos"
    assert clasificacion["proposal_type"] == "new_canonical"
    assert clasificacion["service_candidate"] == "revisión mecánica para compra de auto"
