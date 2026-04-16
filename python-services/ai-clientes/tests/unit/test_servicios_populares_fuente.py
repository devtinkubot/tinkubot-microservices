"""Tests para fuente canónica de servicios populares."""

from types import SimpleNamespace

import pytest

from services.orquestador_conversacion import OrquestadorConversacional


class _SupabaseQueryStub:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _SupabaseStub:
    def __init__(self, data):
        self._data = data

    def table(self, table_name: str):
        assert table_name == "lead_events"
        return _SupabaseQueryStub(self._data)


class _RepositorioLeadEventsStub:
    def __init__(self, data, should_fail=False):
        self._data = data
        self._should_fail = should_fail

    async def obtener_servicios_populares(self, dias: int = 30, limite: int = 5):
        if self._should_fail:
            raise RuntimeError("db error")
        _ = dias
        conteo = {}
        etiqueta_por_clave = {}
        for fila in self._data:
            servicio = ((fila or {}).get("service") or "").strip()
            if not servicio:
                continue
            clave = servicio.lower()
            conteo[clave] = conteo.get(clave, 0) + 1
            etiqueta_por_clave.setdefault(clave, servicio)
        ordenadas = sorted(conteo.items(), key=lambda item: (-item[1], item[0]))
        return [etiqueta_por_clave[k] for k, _ in ordenadas[:limite]]


class _GestorSesionesStub:
    pass


class _RepoFlujoStub:
    async def guardar(self, *args, **kwargs):
        return None


class _RepoClientesStub:
    async def obtener_o_crear(self, *args, **kwargs):
        return {}


class _CallbacksSourceStub:
    async def guardar_flujo(self, *args, **kwargs):
        return None

    async def limpiar_ubicacion_cliente(self, *args, **kwargs):
        return None

    async def limpiar_ciudad_cliente(self, *args, **kwargs):
        return None

    async def limpiar_consentimiento_cliente(self, *args, **kwargs):
        return None

    async def resetear_flujo(self, *args, **kwargs):
        return None

    async def solicitar_consentimiento(self, *args, **kwargs):
        return None

    async def enviar_texto_whatsapp(self, *args, **kwargs):
        return None


def _crear_orquestador(repositorio_lead_events):
    return OrquestadorConversacional(
        redis_client=None,
        gestor_sesiones=_GestorSesionesStub(),
        buscador=object(),
        validador=object(),
        extractor_ia=object(),
        servicio_consentimiento=object(),
        repositorio_flujo=_RepoFlujoStub(),
        repositorio_clientes=_RepoClientesStub(),
        repositorio_lead_events=repositorio_lead_events,
        callbacks_source=_CallbacksSourceStub(),
    )


@pytest.mark.asyncio
async def test_populares_usa_lead_events_service_y_ordena_por_frecuencia(monkeypatch):
    data = [
        {"service": "Plomero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "electricista", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Plomero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Electricista", "created_at": "2026-03-01T00:00:00Z"},
        {"service": "Cerrajero", "created_at": "2026-03-01T00:00:00Z"},
        {"service": " ", "created_at": "2026-03-01T00:00:00Z"},
    ]

    orquestador = _crear_orquestador(_RepositorioLeadEventsStub(data))

    populares = await orquestador.obtener_servicios_populares_recientes(limite=5)

    assert populares[:3] == ["electricista", "Plomero", "Cerrajero"]


@pytest.mark.asyncio
async def test_populares_si_falla_consulta_retorna_lista_vacia(monkeypatch):
    orquestador = _crear_orquestador(
        _RepositorioLeadEventsStub([], should_fail=True)
    )

    populares = await orquestador.obtener_servicios_populares_recientes(limite=5)

    assert populares == []
