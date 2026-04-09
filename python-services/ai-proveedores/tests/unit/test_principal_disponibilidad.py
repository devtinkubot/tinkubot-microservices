import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.availability.processor import (  # noqa: E402
    _registrar_respuesta_disponibilidad_si_aplica,
    _resolver_alias_disponibilidad,
)


class RedisFalso:
    def __init__(self, data=None):
        self.data = data or {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, expire=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


def test_respuesta_disponibilidad_sin_pendientes_no_intercepta():
    redis_falso = RedisFalso()

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, "593999111222@s.whatsapp.net", "1", "onboarding_consent"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_con_lista_vacia_no_intercepta():
    telefono = "593999111223@s.whatsapp.net"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    redis_falso = RedisFalso({clave_pendientes: []})

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "2", "onboarding_city"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_pendiente_valida_registra_accepted():
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

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(redis_falso, telefono, "1")
    )

    assert resultado is not None
    assert "Disponibilidad confirmada" in resultado["messages"][0]["response"]
    assert redis_falso.data[clave_req]["status"] == "accepted"
    assert redis_falso.data[clave_pendientes] == []
    assert redis_falso.data[clave_ciclo]["state"] == "provider_accepted"


def test_respuesta_disponibilidad_boton_valida_registra_rejected():
    telefono = "593999111231@s.whatsapp.net"
    req_id = "search-test-456"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    clave_req = f"availability:request:{req_id}:provider:{telefono}"
    clave_ciclo = f"availability:lifecycle:{req_id}"
    redis_falso = RedisFalso(
        {
            clave_pendientes: [req_id],
            clave_req: {"status": "pending"},
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "availability_reject"
        )
    )

    assert resultado is not None
    assert "no estás disponible" in resultado["messages"][0]["response"].lower()
    assert redis_falso.data[clave_req]["status"] == "rejected"
    assert redis_falso.data[clave_pendientes] == []
    assert redis_falso.data[clave_ciclo]["state"] == "provider_rejected"


def test_resuelve_alias_disponibilidad_a_telefono_canonico():
    telefono_lid = "39101516509235@lid"
    telefono_real = "593998308695@s.whatsapp.net"
    redis_falso = RedisFalso(
        {
            f"availability:alias:{telefono_lid}": {
                "provider_phone": telefono_real,
                "request_id": "search-test",
            }
        }
    )

    resultado = asyncio.run(_resolver_alias_disponibilidad(redis_falso, telefono_lid))

    assert resultado == telefono_real


def test_respuesta_disponibilidad_sin_pendientes_pending_verification_no_intercepta():
    telefono = "593999111225@s.whatsapp.net"
    redis_falso = RedisFalso()

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "pending_verification"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_en_menu_option_devuelve_caducado():
    """En awaiting_menu_option sin pendientes, devuelve mensaje de caducado."""
    telefono = "593999111226@s.whatsapp.net"
    redis_falso = RedisFalso()

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "2", "awaiting_menu_option"
        )
    )

    assert resultado is not None
    assert "caducado" in resultado["messages"][0]["response"].lower()


def test_respuesta_disponibilidad_en_menu_con_contexto_devuelve_caducado():
    """En menú con contexto expecting_response, devuelve mensaje de caducado."""
    telefono = "593999111228@s.whatsapp.net"
    clave_contexto = f"availability:provider:{telefono}:context"
    redis_falso = RedisFalso(
        {
            clave_contexto: {
                "expecting_response": True,
                "request_id": "search-vencido",
            }
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "awaiting_menu_option"
        )
    )

    assert resultado is not None
    assert "caducado" in resultado["messages"][0]["response"].lower()


def test_respuesta_disponibilidad_fuera_onboarding_devuelve_caducado():
    telefono = "593999111229@s.whatsapp.net"
    redis_falso = RedisFalso()

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "searching"
        )
    )

    assert resultado is not None
    assert (
        "tiempo de respuesta ha caducado"
        in resultado["messages"][0]["response"].lower()
    )


def test_respuesta_disponibilidad_en_face_photo_update_no_intercepta():
    """No debe mostrar timeout en awaiting_face_photo_update."""
    telefono = "593999111227@s.whatsapp.net"
    redis_falso = RedisFalso()

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "awaiting_face_photo_update"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_en_completar_perfil_no_intercepta():
    telefono = "593999111230@s.whatsapp.net"
    clave_contexto = f"availability:provider:{telefono}:context"
    redis_falso = RedisFalso(
        {
            clave_contexto: {
                "expecting_response": True,
                "request_id": "search-vencido",
            }
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "onboarding_add_another_service"
        )
    )

    assert resultado is None


def test_respuesta_disponibilidad_en_flujo_activo_con_pendiente_valido_registra():
    telefono = "593999111232@s.whatsapp.net"
    req_id = "search-active-flow-1"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    clave_req = f"availability:request:{req_id}:provider:{telefono}"
    redis_falso = RedisFalso(
        {
            clave_pendientes: [req_id],
            clave_req: {"status": "pending"},
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "1", "onboarding_city"
        )
    )

    assert resultado is not None
    assert redis_falso.data[clave_req]["status"] == "accepted"


def test_respuesta_disponibilidad_recupera_request_id_desde_contexto_corrupto():
    telefono = "593999111233@s.whatsapp.net"
    req_id = "search-context-fallback-1"
    clave_pendientes = f"availability:provider:{telefono}:pending"
    clave_contexto = f"availability:provider:{telefono}:context"
    clave_req = f"availability:request:{req_id}:provider:{telefono}"
    redis_falso = RedisFalso(
        {
            clave_pendientes: "{json-invalido",
            clave_contexto: {"expecting_response": True, "request_id": req_id},
            clave_req: {"status": "pending"},
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(redis_falso, telefono, "1")
    )

    assert resultado is not None
    assert redis_falso.data[clave_req]["status"] == "accepted"


def test_respuesta_disponibilidad_tardia_queda_auditada_sin_contar():
    telefono = "593999111234@s.whatsapp.net"
    req_id = "search-late-response-1"
    clave_contexto = f"availability:provider:{telefono}:context"
    clave_req = f"availability:request:{req_id}:provider:{telefono}"
    clave_ciclo = f"availability:lifecycle:{req_id}"
    redis_falso = RedisFalso(
        {
            clave_contexto: {
                "expecting_response": False,
                "request_id": req_id,
                "status": "expired",
            },
            clave_req: {"status": "expired"},
        }
    )

    resultado = asyncio.run(
        _registrar_respuesta_disponibilidad_si_aplica(
            redis_falso, telefono, "availability_reject", "awaiting_menu_option"
        )
    )

    assert resultado is not None
    assert "caducado" in resultado["messages"][0]["response"].lower()
    assert redis_falso.data[clave_req]["status"] == "expired"
    assert redis_falso.data[clave_req]["late_response_status"] == "rejected"
    assert redis_falso.data[clave_ciclo]["state"] == "expired"
    assert redis_falso.data[clave_ciclo]["late_response_received"] is True
