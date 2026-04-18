from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import pytest

imghdr_stub: Any = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.onboarding.whatsapp_identity import (  # noqa: E402
    persistir_identities_whatsapp,
)
from services.shared.whatsapp_identity import (  # noqa: E402
    clasificar_identidad_whatsapp,
    construir_candidatos_identidad_whatsapp,
    normalizar_identidad_whatsapp,
    normalizar_telefono_canonico,
)


def test_normalizar_telefono_canonico_preserva_bsuid_como_lid():
    assert normalizar_telefono_canonico("", "US.13491208655302741918") == (
        "US.13491208655302741918@lid"
    )


def test_clasificar_identidad_whatsapp_detecta_tipos():
    assert clasificar_identidad_whatsapp("593999111222@s.whatsapp.net") == "phone"
    assert clasificar_identidad_whatsapp("US.13491208655302741918@lid") == "lid"
    assert clasificar_identidad_whatsapp("US.13491208655302741918") == "user_id"


def test_construir_candidatos_identidad_whatsapp_incluye_variantes():
    candidatos = construir_candidatos_identidad_whatsapp(
        "593999111222@s.whatsapp.net"
    )
    assert "593999111222@s.whatsapp.net" in candidatos
    assert "593999111222" in candidatos
    assert "593999111222@lid" in candidatos


@pytest.mark.asyncio
async def test_persistir_identities_whatsapp_upsert_primary_and_aliases(monkeypatch):
    capturados: List[Dict[str, Any]] = []

    class _Query:
        def __init__(self, table_name: str):
            self.table_name = table_name

        def upsert(self, payload, on_conflict=None):
            capturados.append(
                {
                    "table": self.table_name,
                    "payload": dict(payload),
                    "on_conflict": on_conflict,
                }
            )
            return self

        def execute(self):
            return types.SimpleNamespace(data=[{"ok": True}])

    class _SupabaseStub:
        def table(self, table_name):
            return _Query(table_name)

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    monkeypatch.setattr(
        "services.onboarding.whatsapp_identity.run_supabase", _fake_run_supabase
    )

    ok = await persistir_identities_whatsapp(
        _SupabaseStub(),
        "prov-1",
        phone="US.13491208655302741918@lid",
        from_number="US.13491208655302741918@lid",
        user_id="US.13491208655302741918",
        account_id="bot-proveedores",
    )

    assert ok is True
    assert len(capturados) >= 2
    primary = next(
        item
        for item in capturados
        if item["payload"]["identity_value"] == "US.13491208655302741918@lid"
    )
    assert primary["payload"]["is_primary"] is True
    assert primary["payload"]["provider_id"] == "prov-1"
    assert primary["on_conflict"] == "whatsapp_account_id,identity_type,identity_value"

    bsuid = next(
        item for item in capturados if item["payload"]["identity_value"] == "US.13491208655302741918"
    )
    assert bsuid["payload"]["is_primary"] is False
    assert bsuid["payload"]["metadata"]["source"] == "ai-proveedores"
    assert normalizar_identidad_whatsapp("US.13491208655302741918@LID") == (
        "US.13491208655302741918@lid"
    )
