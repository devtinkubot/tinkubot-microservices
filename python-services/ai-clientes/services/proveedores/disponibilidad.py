"""Disponibilidad de proveedores por WhatsApp + Redis."""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ServicioDisponibilidad:
    """Servicio para verificar disponibilidad contactando proveedores."""

    def __init__(self) -> None:
        self.whatsapp_url = os.getenv("WHATSAPP_CLIENTES_URL", "http://wa-gateway:7000")
        self.account_id = os.getenv("WHATSAPP_PROVEEDORES_ACCOUNT_ID", "bot-proveedores")
        self.timeout_seconds = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "45"))
        self.ttl_seconds = int(os.getenv("AVAILABILITY_TTL_SECONDS", "120"))
        self.poll_interval_seconds = float(
            os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1")
        )

    @staticmethod
    def _normalizar_telefono(valor: Optional[str]) -> str:
        if not valor:
            return ""
        telefono = str(valor).strip()
        if "@" in telefono:
            telefono = telefono.split("@", 1)[0]
        return telefono

    @staticmethod
    def _generar_codigo(req_id: str) -> str:
        limpio = re.sub(r"[^A-Za-z0-9]", "", req_id or "")
        if not limpio:
            return "000000"
        return limpio[-6:].upper()

    def _mensaje_disponibilidad(
        self,
        *,
        nombre: str,
        servicio: str,
        ciudad: Optional[str],
        codigo: str,
    ) -> str:
        ciudad_txt = f" en {ciudad}" if ciudad else ""
        return (
            f"Hola {nombre or 'proveedor'}, ¿estás disponible para una solicitud de "
            f"{servicio}{ciudad_txt}?\n\n"
            "Responde:\n"
            "1) Sí, estoy disponible\n"
            "2) No disponible\n\n"
            f"Código: {codigo}"
        )

    async def _enviar_whatsapp(self, *, telefono: str, mensaje: str) -> bool:
        try:
            url = f"{self.whatsapp_url}/send"
            async with httpx.AsyncClient(timeout=10.0) as client:
                respuesta = await client.post(
                    url,
                    json={
                        "account_id": self.account_id,
                        "to": telefono,
                        "message": mensaje,
                    },
                )
            if respuesta.status_code == 200:
                return True
            logger.warning(
                "⚠️ Error enviando disponibilidad a %s: status=%s body=%s",
                telefono,
                respuesta.status_code,
                (respuesta.text or "")[:180],
            )
            return False
        except Exception as exc:
            logger.error("❌ Error enviando disponibilidad a %s: %s", telefono, exc)
            return False

    async def verificar_disponibilidad(
        self,
        *,
        req_id: str,
        servicio: str,
        ciudad: Optional[str],
        candidatos: List[Dict[str, Any]],
        cliente_redis: Any,
    ) -> Dict[str, Any]:
        """
        Verifica disponibilidad consultando por WhatsApp a cada proveedor.
        """
        req_id_real = f"{req_id}-{int(datetime.utcnow().timestamp() * 1000)}"
        codigo = self._generar_codigo(req_id_real)

        logger.info(
            "📍 Verificando disponibilidad: req_id=%s, servicio='%s', ciudad=%s, %s candidatos",
            req_id_real,
            servicio,
            ciudad or "N/A",
            len(candidatos),
        )

        ahora_iso = datetime.utcnow().isoformat()
        candidatos_por_telefono: Dict[str, Dict[str, Any]] = {}

        for candidato in candidatos:
            telefono = self._normalizar_telefono(
                candidato.get("real_phone")
                or candidato.get("phone_number")
                or candidato.get("phone")
            )
            if not telefono:
                continue
            item = dict(candidato)
            item["real_phone"] = telefono
            item.setdefault("provider_id", item.get("id"))
            item.setdefault("nombre", item.get("name") or item.get("full_name"))
            candidatos_por_telefono[telefono] = item

        if not candidatos_por_telefono:
            logger.warning("⚠️ No hay candidatos con teléfono para consultar disponibilidad")
            return {"aceptados": [], "respondidos": [], "tiempo_agotado": False}

        # Publicar solicitudes pendientes y enviar WhatsApp a cada proveedor
        for telefono, candidato in candidatos_por_telefono.items():
            clave_solicitud = f"availability:request:{req_id_real}:provider:{telefono}"
            clave_pendientes = f"availability:provider:{telefono}:pending"

            solicitud = {
                "req_id": req_id_real,
                "code": codigo,
                "provider_phone": telefono,
                "provider_id": candidato.get("provider_id"),
                "provider_name": candidato.get("nombre"),
                "service": servicio,
                "city": ciudad,
                "status": "pending",
                "requested_at": ahora_iso,
            }
            await cliente_redis.set(clave_solicitud, solicitud, expire=self.ttl_seconds)

            pendientes = await cliente_redis.get(clave_pendientes) or []
            if not isinstance(pendientes, list):
                pendientes = []
            if req_id_real not in pendientes:
                pendientes.append(req_id_real)
            await cliente_redis.set(clave_pendientes, pendientes, expire=self.ttl_seconds)

            mensaje = self._mensaje_disponibilidad(
                nombre=str(candidato.get("nombre") or "").strip(),
                servicio=servicio,
                ciudad=ciudad,
                codigo=codigo,
            )
            enviado = await self._enviar_whatsapp(telefono=telefono, mensaje=mensaje)
            if not enviado:
                solicitud["status"] = "failed_to_send"
                await cliente_redis.set(
                    clave_solicitud, solicitud, expire=self.ttl_seconds
                )

        aceptados: List[Dict[str, Any]] = []
        respondidos: List[Dict[str, Any]] = []
        pendientes_telefono = set(candidatos_por_telefono.keys())
        loop = asyncio.get_running_loop()
        fin_espera = loop.time() + self.timeout_seconds

        while pendientes_telefono and loop.time() < fin_espera:
            for telefono in list(pendientes_telefono):
                clave_solicitud = f"availability:request:{req_id_real}:provider:{telefono}"
                estado = await cliente_redis.get(clave_solicitud)
                if not isinstance(estado, dict):
                    pendientes_telefono.discard(telefono)
                    continue

                status = str(estado.get("status") or "").strip().lower()
                if status not in {"accepted", "rejected", "failed_to_send"}:
                    continue

                candidato = candidatos_por_telefono.get(telefono) or {}
                respondido = {
                    "provider_id": candidato.get("provider_id"),
                    "provider_phone": telefono,
                    "status": status,
                    "responded_at": estado.get("responded_at"),
                }
                respondidos.append(respondido)
                if status == "accepted":
                    candidato["availability_confirmed_at"] = (
                        estado.get("responded_at") or datetime.utcnow().isoformat()
                    )
                    aceptados.append(candidato)

                pendientes_telefono.discard(telefono)

            if pendientes_telefono:
                await asyncio.sleep(self.poll_interval_seconds)

        # Limpiar índices pendientes para este req_id
        for telefono in candidatos_por_telefono:
            clave_pendientes = f"availability:provider:{telefono}:pending"
            pendientes = await cliente_redis.get(clave_pendientes) or []
            if not isinstance(pendientes, list):
                continue
            nuevos = [rid for rid in pendientes if rid != req_id_real]
            await cliente_redis.set(clave_pendientes, nuevos, expire=self.ttl_seconds)

        tiempo_agotado = bool(pendientes_telefono)
        if tiempo_agotado:
            logger.info(
                "⏳ Disponibilidad timeout req_id=%s (pendientes=%s)",
                req_id_real,
                len(pendientes_telefono),
            )

        return {
            "aceptados": aceptados,
            "respondidos": respondidos,
            "tiempo_agotado": tiempo_agotado,
        }

    async def start_listener(self) -> None:
        """Compatibilidad con la interfaz anterior."""
        return None


servicio_disponibilidad = ServicioDisponibilidad()
