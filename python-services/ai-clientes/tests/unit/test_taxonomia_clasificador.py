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
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

    monkeypatch.setattr(
        "services.taxonomia.clasificador.run_supabase",
        _fake_run_supabase,
    )

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
                "precision_rule": {
                    "required_dimensions": ["operacion", "tipo de inmueble"],
                    "client_prompt_template": "Indica si buscas comprar, vender o rentar y qué tipo de inmueble.",
                    "sufficient_examples": ["compra de casa"],
                },
            }
        ]
    }

    clasificacion = await clasificar_servicio_taxonomia(
        supabase=_SupabaseStub([]),
        servicio="asesoria inmobiliaria",
        taxonomia=taxonomia,
        audience="client",
    )

    assert clasificacion["domain"] == "inmobiliario"
    assert clasificacion["specificity"] == "insufficient"
    assert clasificacion["missing_dimensions"] == ["operacion", "tipo de inmueble"]
    assert "comprar, vender o rentar" in clasificacion["clarification_question"]


@pytest.mark.asyncio
async def test_clasificar_servicio_taxonomia_retorna_contrato_sufficient(monkeypatch):
    async def _fake_run_supabase(operation, timeout=0, etiqueta=""):
        return operation()

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
                "precision_rule": None,
            }
        ]
    }

    clasificacion = await clasificar_servicio_taxonomia(
        supabase=_SupabaseStub([]),
        servicio="revision mecanica para compra de auto",
        taxonomia=taxonomia,
        audience="client",
    )

    assert clasificacion["domain"] == "vehiculos"
    assert clasificacion["specificity"] == "sufficient"
    assert clasificacion["service_candidate"] == "revisión mecánica para compra de auto"
    assert clasificacion["clarification_question"] is None
