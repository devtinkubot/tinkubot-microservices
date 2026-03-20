import asyncio
from datetime import datetime, timedelta, timezone

import services.registro.limpieza_onboarding_proveedores as limpieza_module
from services.registro.limpieza_onboarding_proveedores import (
    limpiar_onboarding_proveedores,
)


class _Resultado:
    def __init__(self, data):
        self.data = data
        self.error = None


class _QueryEventos:
    def __init__(self, captured):
        self.captured = captured
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.payload = payload
        self.captured.append(payload)
        return self

    def execute(self):
        return _Resultado([{"id": self.payload.get("id", "event-1")}])


class _SupabaseStub:
    def __init__(self, captured):
        self.captured = captured

    def table(self, table_name):
        assert table_name == "provider_onboarding_lifecycle_events"
        return _QueryEventos(self.captured)


class _RedisStub:
    def __init__(self):
        self.keys = set()

    async def set_if_absent(self, key, value, expire=None):
        _ = value, expire
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def delete(self, key):
        self.keys.discard(key)
        return 1


def _proveedor_base(**kwargs):
    ahora = datetime.now(timezone.utc)
    base = {
        "id": "prov-1",
        "phone": "593959091325@s.whatsapp.net",
        "real_phone": "593959091325",
        "full_name": "Ana Pérez",
        "status": "approved_basic",
        "approved_notified_at": (ahora - timedelta(hours=49)).isoformat(),
        "verification_reviewed_at": None,
        "created_at": (ahora - timedelta(hours=49)).isoformat(),
    }
    base.update(kwargs)
    return base


def test_limpieza_onboarding_envia_recordatorio_48h(monkeypatch):
    eventos_insertados = []
    sent_payloads = []

    async def _fake_run_supabase(op, **_kwargs):
        return op()

    async def _fake_send(whatsapp_url, account_id, telefono, payload, metadata):
        sent_payloads.append(
            {
                "whatsapp_url": whatsapp_url,
                "account_id": account_id,
                "telefono": telefono,
                "payload": payload,
                "metadata": metadata,
            }
        )
        return True

    async def _fake_delete(_supabase, _telefono):
        raise AssertionError("No se esperaba eliminación en el recordatorio 48h")

    monkeypatch.setattr(limpieza_module, "run_supabase", _fake_run_supabase)

    resultado = asyncio.run(
        limpiar_onboarding_proveedores(
            _SupabaseStub(eventos_insertados),
            "http://wa-gateway:7000",
            "bot-proveedores",
            candidatos=[_proveedor_base()],
            eventos_existentes=[],
            enviar_whatsapp_fn=_fake_send,
            eliminar_registro_fn=_fake_delete,
            redis_client=_RedisStub(),
        )
    )

    assert resultado["candidates"] == 1
    assert resultado["warnings_sent"] == 1
    assert resultado["expirations_sent"] == 0
    assert resultado["deleted"] == 0
    assert sent_payloads[0]["account_id"] == "bot-proveedores"
    assert sent_payloads[0]["telefono"] == "593959091325@s.whatsapp.net"
    assert sent_payloads[0]["payload"]["ui"]["type"] == "template"
    assert sent_payloads[0]["payload"]["ui"]["template_name"] == (
        "provider_onboarding_warning_48h_v1"
    )
    assert eventos_insertados[0]["event_type"] == "warning_48h"


def test_limpieza_onboarding_expira_72h_y_elimina(monkeypatch):
    eventos_insertados = []
    sent_payloads = []
    eliminaciones = []

    async def _fake_run_supabase(op, **_kwargs):
        return op()

    async def _fake_send(whatsapp_url, account_id, telefono, payload, metadata):
        sent_payloads.append(
            {
                "whatsapp_url": whatsapp_url,
                "account_id": account_id,
                "telefono": telefono,
                "payload": payload,
                "metadata": metadata,
            }
        )
        return True

    async def _fake_delete(supabase, telefono):
        eliminaciones.append((supabase, telefono))
        return {
            "success": True,
            "deleted_from_db": True,
            "deleted_related_services": True,
            "deleted_storage_assets": True,
        }

    monkeypatch.setattr(limpieza_module, "run_supabase", _fake_run_supabase)

    ahora = datetime.now(timezone.utc)
    proveedor = _proveedor_base(
        approved_notified_at=(ahora - timedelta(hours=73)).isoformat(),
        created_at=(ahora - timedelta(hours=73)).isoformat(),
    )

    resultado = asyncio.run(
        limpiar_onboarding_proveedores(
            _SupabaseStub(eventos_insertados),
            "http://wa-gateway:7000",
            "bot-proveedores",
            candidatos=[proveedor],
            eventos_existentes=[],
            enviar_whatsapp_fn=_fake_send,
            eliminar_registro_fn=_fake_delete,
            redis_client=_RedisStub(),
            now_utc=ahora,
        )
    )

    assert resultado["candidates"] == 1
    assert resultado["warnings_sent"] == 0
    assert resultado["expirations_sent"] == 1
    assert resultado["deleted"] == 1
    assert eliminaciones[0][1] == "593959091325@s.whatsapp.net"
    assert sent_payloads[0]["payload"]["ui"]["template_name"] == (
        "provider_onboarding_expired_72h_v1"
    )
    assert eventos_insertados[0]["event_type"] == "expired_72h"
    assert eventos_insertados[0]["metadata"]["deleted_from_db"] is True


def test_limpieza_onboarding_no_repite_evento_existente(monkeypatch):
    eventos_insertados = []
    sent_payloads = []

    async def _fake_run_supabase(op, **_kwargs):
        return op()

    async def _fake_send(*_args, **_kwargs):
        sent_payloads.append(True)
        return True

    async def _fake_delete(_supabase, _telefono):
        raise AssertionError("No se esperaba eliminación cuando ya existe evento")

    monkeypatch.setattr(limpieza_module, "run_supabase", _fake_run_supabase)

    ahora = datetime.now(timezone.utc)
    proveedor = _proveedor_base(
        approved_notified_at=(ahora - timedelta(hours=49)).isoformat(),
        created_at=(ahora - timedelta(hours=49)).isoformat(),
    )

    resultado = asyncio.run(
        limpiar_onboarding_proveedores(
            _SupabaseStub(eventos_insertados),
            "http://wa-gateway:7000",
            "bot-proveedores",
            candidatos=[proveedor],
            eventos_existentes=[{"provider_id": "prov-1", "event_type": "warning_48h"}],
            enviar_whatsapp_fn=_fake_send,
            eliminar_registro_fn=_fake_delete,
            redis_client=_RedisStub(),
            now_utc=ahora,
        )
    )

    assert resultado["skipped_existing_warning"] == 1
    assert resultado["warnings_sent"] == 0
    assert resultado["deleted"] == 0
    assert sent_payloads == []
