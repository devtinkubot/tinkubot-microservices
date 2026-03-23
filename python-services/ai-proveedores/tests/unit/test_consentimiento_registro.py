"""Regresiones del consentimiento final de proveedores."""

from __future__ import annotations

import sys
import types
from typing import Any, Dict

import pytest

from flows.consentimiento.procesador_respuesta import (
    procesar_respuesta_consentimiento,
)
from flows.gestores_estados.gestor_consentimiento import manejar_estado_consentimiento


@pytest.mark.asyncio
async def test_consentimiento_final_crea_proveedor_en_supabase_si_falta_registro(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "awaiting_consent",
        "name": "Proveedor Demo",
        "city": "Cuenca",
        "specialty": "Plomería",
        "services_temporales": ["Plomería"],
        "has_consent": False,
    }

    async def _fake_establecer_flujo(_telefono: str, flujo_guardado: Dict[str, Any]):
        captured["flow"] = dict(flujo_guardado)

    async def _fake_registrar_proveedor_en_base_datos(_supabase, datos_proveedor, *_args, **_kwargs):
        captured["datos_proveedor"] = datos_proveedor
        return {
            "id": "prov-123",
            "phone": datos_proveedor.phone,
            "full_name": datos_proveedor.full_name,
            "city": datos_proveedor.city,
            "has_consent": True,
            "verified": False,
            "status": "pending",
        }

    async def _fake_registrar_consentimiento(*_args, **_kwargs):
        return None

    async def _fake_run_supabase(*_args, **_kwargs):
        return None

    async def _fake_subir_medios_identidad(proveedor_id: str, flujo_guardado: Dict[str, Any]):
        captured["subir_medios"] = {
            "provider_id": proveedor_id,
            "dni_front_image": flujo_guardado.get("dni_front_image"),
            "face_image": flujo_guardado.get("face_image"),
        }

    monkeypatch.setattr(
        "flows.consentimiento.procesador_respuesta.establecer_flujo",
        _fake_establecer_flujo,
    )
    monkeypatch.setattr(
        "flows.consentimiento.procesador_respuesta.registrar_proveedor_en_base_datos",
        _fake_registrar_proveedor_en_base_datos,
    )
    monkeypatch.setattr(
        "flows.consentimiento.registrador.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )
    monkeypatch.setattr(
        "flows.consentimiento.procesador_respuesta.run_supabase",
        _fake_run_supabase,
    )

    respuesta = await procesar_respuesta_consentimiento(
        telefono="593999111222@s.whatsapp.net",
        flujo=flujo,
        carga={
            "selected_option": "1",
            "message": "Acepto",
            "content": "Acepto",
            "timestamp": "2026-03-23T00:00:00Z",
        },
        perfil_proveedor=None,
        subir_medios_fn=_fake_subir_medios_identidad,
    )

    assert captured["datos_proveedor"].phone == "593999111222@s.whatsapp.net"
    assert captured["subir_medios"]["provider_id"] == "prov-123"
    assert captured["flow"]["provider_id"] == "prov-123"
    assert captured["flow"]["has_consent"] is True
    assert captured["flow"]["state"] == "pending_verification"
    assert "revis" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_consentimiento_final_reutiliza_proveedor_existente_y_persiste_medios(
    monkeypatch,
):
    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = object()
    monkeypatch.setitem(sys.modules, "principal", principal_stub)

    captured: Dict[str, Any] = {}
    flujo = {
        "state": "awaiting_consent",
        "id": "prov-999",
        "name": "Proveedor Demo",
        "city": "Cuenca",
        "specialty": "Plomería",
        "services_temporales": ["Plomería"],
        "dni_front_image": "front-b64",
        "face_image": "face-b64",
        "has_consent": False,
    }

    async def _fake_subir_medios_identidad(proveedor_id: str, flujo_guardado: Dict[str, Any]):
        captured["subir_medios"] = {
            "provider_id": proveedor_id,
            "dni_front_image": flujo_guardado.get("dni_front_image"),
            "face_image": flujo_guardado.get("face_image"),
        }

    async def _fake_registrar_consentimiento(*_args, **_kwargs):
        return None

    async def _fake_run_supabase(*_args, **_kwargs):
        return None

    async def _fake_establecer_flujo(_telefono: str, _flujo_guardado: Dict[str, Any]):
        captured["flow_saved"] = True

    monkeypatch.setattr(
        "flows.consentimiento.registrador.registrar_consentimiento",
        _fake_registrar_consentimiento,
    )
    monkeypatch.setattr(
        "flows.consentimiento.procesador_respuesta.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "flows.consentimiento.procesador_respuesta.establecer_flujo",
        _fake_establecer_flujo,
    )

    respuesta = await procesar_respuesta_consentimiento(
        telefono="593999111223@s.whatsapp.net",
        flujo=flujo,
        carga={
            "selected_option": "1",
            "message": "Acepto",
            "content": "Acepto",
            "timestamp": "2026-03-23T00:00:00Z",
        },
        perfil_proveedor={"id": "prov-999", "full_name": "Proveedor Demo"},
        subir_medios_fn=_fake_subir_medios_identidad,
    )

    assert captured["subir_medios"]["provider_id"] == "prov-999"
    assert captured["subir_medios"]["dni_front_image"] == "front-b64"
    assert captured["subir_medios"]["face_image"] == "face-b64"
    assert "revis" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_estado_con_consentimiento_rehidrata_registro_pendiente(
    monkeypatch,
):
    captured: Dict[str, Any] = {}

    async def _fake_asegurar_proveedor_persistido_tras_consentimiento(
        **kwargs,
    ):
        subir_medios_fn = kwargs.get("subir_medios_fn")
        if subir_medios_fn is not None:
            await subir_medios_fn(
                "prov-456",
                {
                    "dni_front_image": "front-b64",
                    "face_image": "face-b64",
                },
            )
        return (
            {
                "id": "prov-456",
                "full_name": "Pendiente de nombre",
                "phone": "593999111222@s.whatsapp.net",
            },
            "prov-456",
        )

    async def _fake_subir_medios_identidad(_provider_id: str, _flujo: Dict[str, Any]):
        captured["upload_called"] = True

    monkeypatch.setattr(
        "flows.gestores_estados.gestor_consentimiento.asegurar_proveedor_persistido_tras_consentimiento",
        _fake_asegurar_proveedor_persistido_tras_consentimiento,
    )

    flujo = {
        "state": "awaiting_consent",
        "has_consent": True,
        "city": "Cuenca",
        "full_name": "",
    }

    respuesta = await manejar_estado_consentimiento(
        flujo=flujo,
        tiene_consentimiento=True,
        esta_registrado=False,
        telefono="593999111222@s.whatsapp.net",
        carga={},
        perfil_proveedor=None,
        subir_medios_identidad=_fake_subir_medios_identidad,
    )

    captured["state"] = flujo["state"]

    assert captured["upload_called"] is True
    assert captured["state"] == "pending_verification"
    assert "revis" in respuesta["messages"][0]["response"].lower()
