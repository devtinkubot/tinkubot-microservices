import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import infrastructure.storage.almacenamiento_imagenes as modulo_almacenamiento  # noqa: E402


class _SupabaseStub:
    def __init__(self):
        self.storage = types.SimpleNamespace(from_=lambda *_args, **_kwargs: None)


def test_subir_medios_identidad_refresca_cache_del_perfil(monkeypatch):
    llamadas = {
        "invalidate": [],
        "refresh": [],
        "upload": [],
        "update": [],
    }

    async def _fake_procesar(_datos_base64, _tipo_archivo):
        return {"bytes": b"img", "extension": "jpg", "mimetype": "image/jpeg"}

    async def _fake_subir_imagen_proveedor(*args):
        llamadas["upload"].append(args)
        return f"https://files.example/{args[2]}.jpg"

    async def _fake_actualizar_imagenes_proveedor(*args):
        llamadas["update"].append(args)
        return True

    async def _fake_obtener_telefono_proveedor(_supabase, _proveedor_id):
        return "593959091325@s.whatsapp.net"

    async def _fake_invalidar_cache_perfil_proveedor(telefono):
        llamadas["invalidate"].append(telefono)
        return True

    async def _fake_refrescar_cache_perfil_proveedor(telefono):
        llamadas["refresh"].append(telefono)

    flows_sesion_stub = types.ModuleType("flows.sesion")
    flows_sesion_stub.invalidar_cache_perfil_proveedor = (
        _fake_invalidar_cache_perfil_proveedor
    )
    flows_sesion_stub.refrescar_cache_perfil_proveedor = (
        _fake_refrescar_cache_perfil_proveedor
    )
    sys.modules["flows.sesion"] = flows_sesion_stub

    monkeypatch.setattr(modulo_almacenamiento, "get_supabase_client", lambda: _SupabaseStub())
    monkeypatch.setattr(
        modulo_almacenamiento,
        "procesar_imagen_base64_con_metadata",
        _fake_procesar,
    )
    monkeypatch.setattr(
        modulo_almacenamiento,
        "subir_imagen_proveedor",
        _fake_subir_imagen_proveedor,
    )
    monkeypatch.setattr(
        modulo_almacenamiento,
        "actualizar_imagenes_proveedor",
        _fake_actualizar_imagenes_proveedor,
    )
    monkeypatch.setattr(
        modulo_almacenamiento,
        "_obtener_telefono_proveedor",
        _fake_obtener_telefono_proveedor,
    )

    asyncio.run(
        modulo_almacenamiento.subir_medios_identidad(
            "prov-1",
            {"dni_front_image": "front", "face_image": "face"},
        )
    )

    assert llamadas["upload"] == [
        ("prov-1", b"img", "dni-front", "jpg", "image/jpeg", "prov-1"),
        ("prov-1", b"img", "face", "jpg", "image/jpeg", "prov-1"),
    ]
    assert llamadas["update"] == [
        ("prov-1", "https://files.example/dni-front.jpg", "https://files.example/face.jpg"),
    ]
    assert llamadas["invalidate"] == ["593959091325@s.whatsapp.net"]
    assert llamadas["refresh"] == ["593959091325@s.whatsapp.net"]


def test_subir_medios_identidad_usa_identificador_estable_cuando_no_hay_provider_id(
    monkeypatch,
):
    llamadas = {
        "upload": [],
        "update": [],
    }

    async def _fake_procesar(_datos_base64, _tipo_archivo):
        return {"bytes": b"img", "extension": "jpg", "mimetype": "image/jpeg"}

    async def _fake_subir_imagen_proveedor(*args):
        llamadas["upload"].append(args)
        return f"https://files.example/{args[5]}/{args[2]}.jpg"

    async def _fake_actualizar_imagenes_proveedor(*args):
        llamadas["update"].append(args)
        return True

    monkeypatch.setattr(modulo_almacenamiento, "get_supabase_client", lambda: _SupabaseStub())
    monkeypatch.setattr(
        modulo_almacenamiento,
        "procesar_imagen_base64_con_metadata",
        _fake_procesar,
    )
    monkeypatch.setattr(
        modulo_almacenamiento,
        "subir_imagen_proveedor",
        _fake_subir_imagen_proveedor,
    )
    monkeypatch.setattr(
        modulo_almacenamiento,
        "actualizar_imagenes_proveedor",
        _fake_actualizar_imagenes_proveedor,
    )

    flujo = {
        "phone": "593969648465@s.whatsapp.net",
        "dni_front_image": "front",
        "face_image": "face",
    }

    asyncio.run(
        modulo_almacenamiento.subir_medios_identidad(
            None,
            flujo,
        )
    )

    assert llamadas["upload"] == [
        ("593969648465", b"img", "dni-front", "jpg", "image/jpeg", "593969648465"),
        ("593969648465", b"img", "face", "jpg", "image/jpeg", "593969648465"),
    ]
    assert llamadas["update"] == []
    assert flujo["dni_front_photo_url"] == "https://files.example/593969648465/dni-front.jpg"
    assert flujo["face_photo_url"] == "https://files.example/593969648465/face.jpg"
    assert "dni_front_image" not in flujo
    assert "face_image" not in flujo
