"""Tests del ciclo de vida de solicitudes de disponibilidad."""

import pytest

from services.proveedores.disponibilidad import ServicioDisponibilidad


class RedisFalso:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, expire=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


class RedisRawFalso:
    def __init__(self, data):
        self.data = data

    async def set(self, key, value, nx=False, ex=None):
        _ = ex
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def eval(self, script, numkeys, key, value):
        _ = script, numkeys
        if self.data.get(key) == value:
            self.data.pop(key, None)
            return 1
        return 0


class RedisFalsoConLock(RedisFalso):
    def __init__(self):
        super().__init__()
        self.redis_client = RedisRawFalso(self.data)


@pytest.mark.asyncio
async def test_verificar_disponibilidad_sin_candidatos_cierra_ciclo():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalso()

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-prueba",
        servicio="plomero",
        ciudad="Quito",
        descripcion_problema="fuga de agua",
        candidatos=[],
        cliente_redis=redis_falso,
    )

    request_id = resultado.get("request_id")
    assert request_id

    clave_ciclo = f"availability:lifecycle:{request_id}"
    ciclo = redis_falso.data.get(clave_ciclo)
    assert ciclo["state"] == "closed"
    assert ciclo["close_reason"] == "no_candidates"


@pytest.mark.asyncio
async def test_marcar_presentada_y_cerrar_solicitud_actualiza_ciclo():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalso()
    request_id = "search-prueba-123"

    await servicio.marcar_solicitud_como_presentada(
        request_id=request_id,
        cliente_redis=redis_falso,
        telefono_cliente="+593999111111",
        proveedores_presentados=2,
    )

    clave_ciclo = f"availability:lifecycle:{request_id}"
    assert redis_falso.data[clave_ciclo]["state"] == "presented_to_customer"
    assert redis_falso.data[clave_ciclo]["presented_providers_count"] == 2

    await servicio.cerrar_solicitud(
        request_id=request_id,
        cliente_redis=redis_falso,
        motivo="finalizado",
    )
    assert redis_falso.data[clave_ciclo]["state"] == "closed"
    assert redis_falso.data[clave_ciclo]["close_reason"] == "finalizado"


@pytest.mark.asyncio
async def test_timeout_envia_push_proactivo_de_caducidad():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalsoConLock()
    mensajes_enviados = []

    async def enviar_whatsapp_falso(*, telefono: str, mensaje: str) -> bool:
        mensajes_enviados.append({"telefono": telefono, "mensaje": mensaje})
        return True

    servicio._enviar_whatsapp = enviar_whatsapp_falso  # type: ignore[method-assign]
    servicio.timeout_seconds = 0
    servicio.grace_seconds = 0
    servicio.poll_interval_seconds = 0

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-timeout",
        servicio="tapicería",
        ciudad="Cuenca",
        descripcion_problema="refacción de muebles de sala",
        candidatos=[
            {
                "provider_id": "prov-1",
                "name": "Proveedor Uno",
                "real_phone": "593999000001",
            }
        ],
        cliente_redis=redis_falso,
    )

    assert resultado["tiempo_agotado"] is True
    assert resultado["aceptados"] == []

    mensajes_caducidad = [
        m for m in mensajes_enviados if "solicitud *caducó*" in m["mensaje"]
    ]
    assert len(mensajes_caducidad) == 1
    assert mensajes_caducidad[0]["telefono"] == "593999000001@s.whatsapp.net"


@pytest.mark.asyncio
async def test_verificar_disponibilidad_cierra_si_todos_ocupados():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalso()
    redis_falso.data["availability:provider:593999000001@s.whatsapp.net:pending"] = [
        "req-previo"
    ]
    mensajes_enviados = []

    async def enviar_whatsapp_falso(*, telefono: str, mensaje: str) -> bool:
        mensajes_enviados.append({"telefono": telefono, "mensaje": mensaje})
        return True

    servicio._enviar_whatsapp = enviar_whatsapp_falso  # type: ignore[method-assign]

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-ocupados",
        servicio="tapicería",
        ciudad="Cuenca",
        descripcion_problema="refacción de muebles de sala",
        candidatos=[
            {
                "provider_id": "prov-ocupado",
                "name": "Proveedor Ocupado",
                "real_phone": "593999000001",
            }
        ],
        cliente_redis=redis_falso,
    )

    assert resultado["aceptados"] == []
    assert resultado["respondidos"] == []
    assert resultado["tiempo_agotado"] is False
    assert resultado["excluded_busy_providers_count"] == 1
    assert mensajes_enviados == []

    request_id = resultado["request_id"]
    clave_ciclo = f"availability:lifecycle:{request_id}"
    ciclo = redis_falso.data[clave_ciclo]
    assert ciclo["state"] == "closed"
    assert ciclo["close_reason"] == "all_providers_busy"


@pytest.mark.asyncio
async def test_verificar_disponibilidad_excluye_ocupados_y_consulta_libres():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalsoConLock()
    redis_falso.data["availability:provider:593999000001@s.whatsapp.net:pending"] = [
        "req-previo"
    ]
    mensajes_enviados = []

    async def enviar_whatsapp_falso(*, telefono: str, mensaje: str) -> bool:
        mensajes_enviados.append({"telefono": telefono, "mensaje": mensaje})
        return True

    servicio._enviar_whatsapp = enviar_whatsapp_falso  # type: ignore[method-assign]
    servicio.timeout_seconds = 0
    servicio.grace_seconds = 0
    servicio.poll_interval_seconds = 0

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-mixto",
        servicio="tapicería",
        ciudad="Cuenca",
        descripcion_problema="refacción de muebles de sala",
        candidatos=[
            {
                "provider_id": "prov-ocupado",
                "name": "Proveedor Ocupado",
                "real_phone": "593999000001",
            },
            {
                "provider_id": "prov-libre",
                "name": "Proveedor Libre",
                "real_phone": "593999000002",
            },
        ],
        cliente_redis=redis_falso,
    )

    assert resultado["excluded_busy_providers_count"] == 1
    telefonos_contactados = {m["telefono"] for m in mensajes_enviados}
    assert "593999000001@s.whatsapp.net" not in telefonos_contactados
    assert "593999000002@s.whatsapp.net" in telefonos_contactados


@pytest.mark.asyncio
async def test_lock_atomico_descarta_proveedor_ocupado():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalsoConLock()
    telefono = "593999000010@s.whatsapp.net"
    redis_falso.data[f"availability:provider:{telefono}:lock"] = "otra-solicitud"
    mensajes_enviados = []

    async def enviar_whatsapp_falso(*, telefono: str, mensaje: str) -> bool:
        mensajes_enviados.append({"telefono": telefono, "mensaje": mensaje})
        return True

    servicio._enviar_whatsapp = enviar_whatsapp_falso  # type: ignore[method-assign]

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-lock-ocupado",
        servicio="electricista",
        ciudad="Cuenca",
        descripcion_problema="revisión de tablero",
        candidatos=[
            {
                "provider_id": "prov-lock-ocupado",
                "name": "Proveedor Lock",
                "real_phone": "593999000010",
            }
        ],
        cliente_redis=redis_falso,
    )

    assert resultado["aceptados"] == []
    assert resultado["tiempo_agotado"] is False
    assert resultado["lock_busy_skip_count"] == 1
    assert resultado["lock_acquired_count"] == 0
    assert mensajes_enviados == []


@pytest.mark.asyncio
async def test_lock_atomico_se_libera_al_finalizar():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalsoConLock()
    servicio.timeout_seconds = 0
    servicio.grace_seconds = 0
    servicio.poll_interval_seconds = 0

    async def enviar_whatsapp_falso(*, telefono: str, mensaje: str) -> bool:
        _ = telefono, mensaje
        return True

    servicio._enviar_whatsapp = enviar_whatsapp_falso  # type: ignore[method-assign]

    resultado = await servicio.verificar_disponibilidad(
        req_id="search-lock-release",
        servicio="pintor",
        ciudad="Cuenca",
        descripcion_problema="pintar sala",
        candidatos=[
            {
                "provider_id": "prov-lock-libre",
                "name": "Proveedor Libre",
                "real_phone": "593999000011",
            }
        ],
        cliente_redis=redis_falso,
    )

    assert resultado["lock_acquired_count"] == 1
    lock_key = "availability:provider:593999000011@s.whatsapp.net:lock"
    assert lock_key not in redis_falso.data


@pytest.mark.asyncio
async def test_lock_release_owner_mismatch_no_libera():
    servicio = ServicioDisponibilidad()
    redis_falso = RedisFalsoConLock()
    telefono = "593999000012@s.whatsapp.net"
    lock_key = f"availability:provider:{telefono}:lock"
    redis_falso.data[lock_key] = "req-original"

    await servicio._liberar_lock_proveedor(
        cliente_redis=redis_falso,
        telefono=telefono,
        request_id="req-distinto",
    )

    assert redis_falso.data.get(lock_key) == "req-original"
