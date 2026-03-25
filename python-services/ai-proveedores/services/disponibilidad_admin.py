"""Rutas admin para inspección de disponibilidad de proveedores."""

from typing import Any, Dict, Optional

from config import configuracion
from fastapi import APIRouter, Header

from infrastructure.redis import cliente_redis
from services.availability import (
    CLAVE_CICLO_SOLICITUD,
    CLAVE_CONTEXTO_DISPONIBILIDAD,
    CLAVE_PENDIENTES_DISPONIBILIDAD,
)

router = APIRouter()


def _normalizar_jid(valor: str) -> Optional[str]:
    texto = (valor or "").strip()
    if "@" not in texto:
        return None

    user, server = texto.split("@", 1)
    user = user.strip()
    server = server.strip().lower()
    if not user or not server:
        return None
    return f"{user}@{server}"


def _extraer_user_jid(valor: str) -> str:
    texto = (valor or "").strip()
    if not texto:
        return ""
    if "@" in texto:
        return texto.split("@", 1)[0].strip()
    return texto


def _resolver_telefono_canonico(raw_from: str, raw_phone: str) -> str:
    jid = _normalizar_jid(raw_from) or _normalizar_jid(raw_phone)
    if jid:
        return jid

    user = _extraer_user_jid(raw_phone)
    if not user:
        return ""
    return f"{user}@s.whatsapp.net"


@router.get("/availability-lifecycle/{request_id}")
async def obtener_ciclo_disponibilidad(
    request_id: str,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """Consulta el estado del ciclo de una solicitud por `request_id`."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    request_id_limpio = (request_id or "").strip()
    if not request_id_limpio:
        return {"success": False, "message": "request_id is required"}

    ciclo = await cliente_redis.get(CLAVE_CICLO_SOLICITUD.format(request_id_limpio))
    return {
        "success": True,
        "request_id": request_id_limpio,
        "exists": bool(ciclo),
        "lifecycle": ciclo or {},
    }


@router.get("/availability-provider-state")
async def obtener_estado_disponibilidad_proveedor(
    phone: str,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """Consulta pendientes, contexto y ciclos de disponibilidad por proveedor."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    telefono_crudo = (phone or "").strip()
    if not telefono_crudo:
        return {"success": False, "message": "phone is required"}

    telefono = _resolver_telefono_canonico(telefono_crudo, telefono_crudo)
    if not telefono:
        return {"success": False, "message": "invalid phone format"}

    contexto = await cliente_redis.get(CLAVE_CONTEXTO_DISPONIBILIDAD.format(telefono))
    pendientes = await cliente_redis.get(
        CLAVE_PENDIENTES_DISPONIBILIDAD.format(telefono)
    )
    if not isinstance(pendientes, list):
        pendientes = []

    request_ids = []
    if isinstance(contexto, dict) and contexto.get("request_id"):
        request_ids.append(str(contexto["request_id"]))
    request_ids.extend([str(rid) for rid in pendientes if rid])
    request_ids_unicos = list(dict.fromkeys(request_ids))

    ciclos = {}
    for rid in request_ids_unicos:
        ciclos[rid] = await cliente_redis.get(CLAVE_CICLO_SOLICITUD.format(rid)) or {}

    return {
        "success": True,
        "provider_phone": telefono,
        "context": contexto or {},
        "pending_request_ids": request_ids_unicos,
        "lifecycles": ciclos,
    }
