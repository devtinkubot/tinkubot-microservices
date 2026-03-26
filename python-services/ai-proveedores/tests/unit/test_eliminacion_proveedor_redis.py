import asyncio

import services.onboarding.registration.eliminacion_proveedor as eliminacion_module
from services.onboarding.registration.eliminacion_proveedor import (
    eliminar_registro_proveedor,
)


class _Resultado:
    def __init__(self, data=None):
        self.data = data or []
        self.error = None


class _Query:
    def __init__(self, captured, table_name):
        self.captured = captured
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def delete(self):
        self.captured.append((self.table_name, "delete"))
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "providers":
            return _Resultado(
                [
                    {
                        "id": "prov-1",
                        "dni_front_photo_url": None,
                        "dni_back_photo_url": None,
                        "face_photo_url": None,
                    }
                ]
            )
        return _Resultado([])


class _StorageBucket:
    def __init__(self, captured):
        self.captured = captured

    def remove(self, rutas):
        self.captured.append(("storage.remove", tuple(rutas)))
        return _Resultado([])


class _Storage:
    def __init__(self, captured):
        self.captured = captured

    def from_(self, bucket):
        self.captured.append(("storage.bucket", bucket))
        return _StorageBucket(self.captured)


class _SupabaseStub:
    def __init__(self, captured):
        self.captured = captured
        self.storage = _Storage(captured)

    def table(self, table_name):
        self.captured.append(("table", table_name))
        return _Query(self.captured, table_name)


def test_eliminacion_proveedor_limpia_marca_redis(monkeypatch):
    captured = []

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    async def _fake_marcar_perfil_eliminado(telefono):
        captured.append(("mark_deleted", telefono))
        return True

    async def _fake_limpiar_marca_perfil_eliminado(telefono):
        captured.append(("clear_deleted", telefono))
        return True

    async def _fake_limpiar_claves_proveedor(telefono):
        captured.append(("clear_provider_keys", telefono))
        return 1

    async def _fake_reiniciar_flujo(telefono):
        captured.append(("reset_flow", telefono))
        return None

    monkeypatch.setattr(eliminacion_module, "run_supabase", _fake_run_supabase)

    monkeypatch.setattr(
        eliminacion_module,
        "marcar_perfil_eliminado",
        _fake_marcar_perfil_eliminado,
    )
    monkeypatch.setattr(
        eliminacion_module,
        "limpiar_marca_perfil_eliminado",
        _fake_limpiar_marca_perfil_eliminado,
    )
    monkeypatch.setattr(
        eliminacion_module,
        "limpiar_claves_proveedor",
        _fake_limpiar_claves_proveedor,
    )
    monkeypatch.setattr(
        eliminacion_module,
        "reiniciar_flujo",
        _fake_reiniciar_flujo,
    )

    resultado = asyncio.run(
        eliminar_registro_proveedor(
            _SupabaseStub(captured),
            "593959091325@s.whatsapp.net",
        )
    )

    assert resultado["success"] is True
    assert ("mark_deleted", "593959091325@s.whatsapp.net") in captured
    assert ("clear_deleted", "593959091325@s.whatsapp.net") in captured
    assert ("clear_provider_keys", "593959091325@s.whatsapp.net") in captured
    assert ("reset_flow", "593959091325@s.whatsapp.net") in captured
