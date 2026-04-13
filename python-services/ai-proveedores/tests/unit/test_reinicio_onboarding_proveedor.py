import asyncio
from datetime import datetime, timedelta, timezone

import services.onboarding.registration.reinicio_onboarding_proveedor as reinicio_module
from services.onboarding.registration.reinicio_onboarding_proveedor import (
    reiniciar_onboarding_proveedor,
)


class _Resultado:
    def __init__(self, data=None):
        self.data = data or []
        self.error = None


class _Query:
    def __init__(self, table_name, captured):
        self.table_name = table_name
        self.captured = captured
        self.operation = "select"
        self.payload = None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        self.captured.append((self.table_name, "insert", payload))
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = payload
        self.captured.append((self.table_name, "upsert", payload))
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        self.captured.append((self.table_name, "update", payload))
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "providers":
            now = datetime.now(timezone.utc)
            return _Resultado(
                [
                    {
                        "id": "prov-1",
                        "phone": "593959091325@s.whatsapp.net",
                        "real_phone": "593959091325",
                        "full_name": "Ana Pérez",
                        "status": "approved",
                        "onboarding_step": None,
                        "approved_notified_at": (now - timedelta(hours=50)).isoformat(),
                        "verification_reviewed_at": None,
                        "created_at": (now - timedelta(hours=50)).isoformat(),
                    }
                ]
            )
        return _Resultado([{"id": "event-1"}])


class _SupabaseStub:
    def __init__(self, captured):
        self.captured = captured

    def table(self, table_name):
        return _Query(table_name, self.captured)


def test_reinicio_onboarding_proveedor_envia_72h_y_elimina(monkeypatch):
    captured = []
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

    async def _fake_delete(supabase, telefono, provider_id=None):
        eliminaciones.append(
            {
                "supabase": supabase,
                "telefono": telefono,
                "provider_id": provider_id,
            }
        )
        return {
            "success": True,
            "deleted_from_db": True,
            "deleted_from_cache": True,
            "deleted_related_services": True,
            "deleted_storage_assets": True,
        }

    monkeypatch.setattr(reinicio_module, "run_supabase", _fake_run_supabase)
    monkeypatch.setattr(reinicio_module, "_enviar_whatsapp", _fake_send)
    monkeypatch.setattr(
        reinicio_module,
        "eliminar_registro_proveedor",
        _fake_delete,
    )

    resultado = asyncio.run(
        reiniciar_onboarding_proveedor(
            _SupabaseStub(captured),
            "prov-1",
            "http://wa-gateway:7000",
            "bot-proveedores",
        )
    )

    assert resultado["success"] is True
    assert resultado["providerId"] == "prov-1"
    assert resultado["deleted_from_db"] is True
    assert resultado["sent_whatsapp"] is True
    assert sent_payloads[0]["payload"]["ui"]["template_name"] == (
        "provider_reset_v1"
    )
    assert sent_payloads[0]["payload"]["response"] == (
        "La informacion ingresada es insuficiente. "
        "Si quieres retomar nuevamente, inicia un nuevo registro."
    )
    assert sent_payloads[0]["payload"]["ui"]["template_components"][0] == {
        "type": "body",
        "parameters": [],
    }
    assert sent_payloads[0]["payload"]["ui"]["template_components"][1] == {
        "type": "button",
        "sub_type": "quick_reply",
        "index": "0",
        "parameters": [{"type": "payload", "payload": "registro"}],
    }
    assert eliminaciones[0]["provider_id"] == "prov-1"
    assert eliminaciones[0]["telefono"] == "593959091325@s.whatsapp.net"
    assert any(
        entry[0] == "provider_onboarding_lifecycle_events"
        and entry[1] == "upsert"
        for entry in captured
    )
    assert any(
        entry[0] == "provider_onboarding_lifecycle_events"
        and entry[1] == "update"
        for entry in captured
    )
