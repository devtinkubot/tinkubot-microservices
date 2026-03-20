"""Regresiones para el programador de retroalimentación."""

from types import SimpleNamespace

import pytest
from services.programador_retroalimentacion import ProgramadorRetroalimentacion


class _QuerySupabaseFalso:
    def __init__(self):
        self.inserted_payload = None

    def insert(self, payload):
        self.inserted_payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=self.inserted_payload)


class _SupabaseFalso:
    def __init__(self):
        self.query = _QuerySupabaseFalso()

    def table(self, _name: str):
        return self.query


class _RepoFlujoFalso:
    def __init__(self):
        self.last_saved = None

    async def obtener(self, _telefono: str):
        return {}

    async def guardar(self, _telefono: str, datos: dict):
        self.last_saved = dict(datos)


@pytest.mark.asyncio
async def test_programar_solicitud_retroalimentacion_usa_primer_nombre():
    supabase = _SupabaseFalso()
    programador = ProgramadorRetroalimentacion(
        supabase=supabase,
        repositorio_flujo=_RepoFlujoFalso(),
        whatsapp_url="http://whatsapp.local",
        whatsapp_account_id="bot-clientes",
        retraso_retroalimentacion_segundos=30,
        intervalo_sondeo_tareas_segundos=5,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    await programador.programar_solicitud_retroalimentacion(
        telefono="593999111222",
        proveedor={"name": "Diego Unkuch Gonzalez"},
        lead_event_id="lead-1",
    )

    payload = supabase.query.inserted_payload
    assert payload is not None
    assert payload["payload"]["provider_name"] == "Diego"
    assert payload["payload"]["message"] == (
        "*¿Cómo te fue con Diego?*\n\n"
        "*Calificar a nuestros expertos nos ayuda a mejorar el servicio "
        "que te entregamos. Tu opinión hace la diferencia y nos toma "
        "muy poco tiempo.*\n\n"
        "*Responde con el número de tu opción:*\n\n"
        "*1.* ⭐ Excelente\n"
        "*2.* ✓ Bien\n"
        "*3.* 😐 Regular\n"
        "*4.* ✗ No lo contraté\n"
        "*5.* ❌ Mal servicio\n"
        "*6.* Prefiero no responder\n\n"
        "Por favor elige una opción de la lista."
    )
    assert payload["payload"]["ui"]["options"][-1]["id"] == "prefer_not_to_answer"
