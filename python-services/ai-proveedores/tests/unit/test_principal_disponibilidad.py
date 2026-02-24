import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import principal


class RedisFalso:
    def __init__(self, data=None):
        self.data = data or {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, expire=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


def test_respuesta_disponibilidad_sin_pendientes_no_intercepta(monkeypatch):
    redis_falso = RedisFalso()
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            "593999111222@s.whatsapp.net", "1", "awaiting_consent"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_con_lista_vacia_no_intercepta(monkeypatch):
    telefono = "593999111223@s.whatsapp.net"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    redis_falso = RedisFalso({clave_pendientes: []})
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            telefono, "2", "awaiting_city"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_pendiente_valida_registra_accepted(monkeypatch):
    telefono = "593999111224@s.whatsapp.net"
    req_id = "search-test-123"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    clave_req = f"availability:request:{req_id}:provider:{telefono}"
    clave_ciclo = f"availability:lifecycle:{req_id}"
    redis_falso = RedisFalso(
        {
            clave_pendientes: [req_id],
            clave_req: {"status": "pending"},
        }
    )
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(telefono, "1")
    )

    assert resultado is not None
    assert "Disponibilidad confirmada" in resultado["messages"][0]["response"]
    assert redis_falso.data[clave_req]["status"] == "accepted"
    assert redis_falso.data[clave_pendientes] == []
    assert redis_falso.data[clave_ciclo]["state"] == "provider_accepted"


def test_respuesta_disponibilidad_sin_pendientes_en_menu_devuelve_caducado(monkeypatch):
    telefono = "593999111225@s.whatsapp.net"
    redis_falso = RedisFalso()
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            telefono, "1", "pending_verification"
        )
    )

    assert resultado is not None
    assert "tiempo de respuesta ha caducado" in resultado["messages"][0][
        "response"
    ].lower()


def test_respuesta_disponibilidad_en_menu_option_no_intercepta(monkeypatch):
    """Cuando el estado es awaiting_menu_option, NO debe mostrarse mensaje de timeout."""
    telefono = "593999111226@s.whatsapp.net"
    redis_falso = RedisFalso()
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            telefono, "2", "awaiting_menu_option"
        )
    )

    # No debe interceptar - debe dejar que el flujo de menú continúe
    assert resultado is None


def test_respuesta_disponibilidad_en_menu_con_contexto_devuelve_caducado(monkeypatch):
    """Si había contexto de disponibilidad, una respuesta 1/2 no debe entrar al menú."""
    telefono = "593999111228@s.whatsapp.net"
    clave_contexto = f"availability:provider:{telefono}:context"
    clave_ciclo = "availability:lifecycle:search-vencido"
    redis_falso = RedisFalso(
        {
            clave_contexto: {
                "expecting_response": True,
                "request_id": "search-vencido",
            }
        }
    )
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            telefono, "1", "awaiting_menu_option"
        )
    )

    assert resultado is not None
    assert "tiempo de respuesta ha caducado" in resultado["messages"][0][
        "response"
    ].lower()
    assert redis_falso.data[clave_ciclo]["state"] == "expired"


def test_respuesta_disponibilidad_en_face_photo_update_no_intercepta(monkeypatch):
    """Cuando el estado es awaiting_face_photo_update, NO debe mostrarse mensaje de timeout."""
    telefono = "593999111227@s.whatsapp.net"
    redis_falso = RedisFalso()
    monkeypatch.setattr(principal, "cliente_redis", redis_falso)

    resultado = asyncio.run(
        principal._registrar_respuesta_disponibilidad_si_aplica(
            telefono, "1", "awaiting_face_photo_update"
        )
    )

    assert resultado is None
