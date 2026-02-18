"""Disponibilidad de proveedores por WhatsApp + Redis."""

import asyncio
import json
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
        self.account_id = os.getenv(
            "WHATSAPP_PROVEEDORES_ACCOUNT_ID", "bot-proveedores"
        )
        self.timeout_seconds = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "60"))
        self.ttl_seconds = int(os.getenv("AVAILABILITY_TTL_SECONDS", "120"))
        self.send_timeout_seconds = float(
            os.getenv("AVAILABILITY_SEND_TIMEOUT_SECONDS", "10")
        )
        self.max_send_concurrency = int(
            os.getenv("AVAILABILITY_MAX_SEND_CONCURRENCY", "50")
        )
        self.poll_interval_seconds = float(
            os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1")
        )
        self.grace_seconds = float(os.getenv("AVAILABILITY_GRACE_SECONDS", "8"))
        self._client = httpx.AsyncClient(
            timeout=self.send_timeout_seconds,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=100),
        )
        self._send_semaphore = asyncio.Semaphore(self.max_send_concurrency)

    @staticmethod
    def _decode_if_json_string(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @staticmethod
    def _formatear_telefono_whatsapp(valor: Optional[str]) -> Optional[str]:
        """
        Formatea teléfono para WhatsApp:
        - Si ya tiene @, lo usa tal cual
        - Si es LID (>=15 dígitos sin código de país conocido) → @lid
        - Si es teléfono normal → @s.whatsapp.net
        """
        if not valor:
            return None

        telefono = str(valor).strip()
        if not telefono:
            return None

        # Ya tiene formato JID - normalizar servidor y usar tal cual
        if "@" in telefono:
            user, server = telefono.split("@", 1)
            user = user.strip()
            server = server.strip().lower()
            if not user or not server:
                return None
            return f"{user}@{server}"

        # Extraer solo dígitos
        digitos = re.sub(r"\D", "", telefono)
        if not digitos:
            return None

        # Códigos de país comunes
        codigos_pais = {"593", "54", "52", "57", "56", "51", "507", "502", "503", "505"}
        es_telefono_normal = (
            any(digitos.startswith(c) for c in codigos_pais) and len(digitos) <= 13
        )

        # LID: >= 15 dígitos y no es teléfono normal
        if len(digitos) >= 15 and not es_telefono_normal:
            return f"{digitos}@lid"

        return f"{digitos}@s.whatsapp.net"

    def _mensaje_disponibilidad_contexto(
        self,
        *,
        nombre: str,
        servicio: str,
        ciudad: Optional[str],
        descripcion_problema: Optional[str],
    ) -> str:
        ciudad_txt = ciudad or "tu ciudad"
        detalle = (descripcion_problema or "").strip() or servicio
        return (
            f"¡Hola *{nombre or 'proveedor'}*!\n"
            f"¿Estás disponible para atender en *{ciudad_txt}*?\n\n"
            f"Servicio requerido: *{servicio}*\n\n"
            f"Para atender: *{detalle}*"
        )

    @staticmethod
    def _mensaje_disponibilidad_opciones() -> str:
        return (
            "*Responde con el número de tu opción:*\n\n"
            "*1.* Sí, estoy disponible\n"
            "*2.* No disponible"
        )

    async def _enviar_whatsapp(self, *, telefono: str, mensaje: str) -> bool:
        try:
            url = f"{self.whatsapp_url}/send"
            async with self._send_semaphore:
                respuesta = await self._client.post(
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

    async def _registrar_y_enviar_a_proveedor(
        self,
        *,
        req_id_real: str,
        servicio: str,
        ciudad: Optional[str],
        descripcion_problema: Optional[str],
        telefono: str,
        candidato: Dict[str, Any],
        ahora_iso: str,
        cliente_redis: Any,
    ) -> None:
        # phone canónico JID completo para correlación exacta solicitud-respuesta.
        clave_solicitud = f"availability:request:{req_id_real}:provider:{telefono}"
        clave_pendientes = f"availability:provider:{telefono}:pending"

        solicitud = {
            "req_id": req_id_real,
            "provider_phone": telefono,
            "provider_id": candidato.get("provider_id"),
            "provider_name": candidato.get("nombre"),
            "service": servicio,
            "city": ciudad,
            "problem_description": (descripcion_problema or "").strip(),
            "status": "pending",
            "requested_at": ahora_iso,
        }
        await cliente_redis.set(clave_solicitud, solicitud, expire=self.ttl_seconds)

        pendientes = await cliente_redis.get(clave_pendientes) or []
        pendientes = self._decode_if_json_string(pendientes)
        if not isinstance(pendientes, list):
            pendientes = []
        if req_id_real not in pendientes:
            pendientes.append(req_id_real)
        await cliente_redis.set(clave_pendientes, pendientes, expire=self.ttl_seconds)

        mensaje_contexto = self._mensaje_disponibilidad_contexto(
            nombre=str(candidato.get("nombre") or "").strip(),
            servicio=servicio,
            ciudad=ciudad,
            descripcion_problema=descripcion_problema,
        )
        mensaje_opciones = self._mensaje_disponibilidad_opciones()

        enviado_contexto = await self._enviar_whatsapp(
            telefono=telefono, mensaje=mensaje_contexto
        )
        if not enviado_contexto:
            solicitud["status"] = "failed_to_send"
            await cliente_redis.set(clave_solicitud, solicitud, expire=self.ttl_seconds)
            return

        enviado_opciones = await self._enviar_whatsapp(
            telefono=telefono, mensaje=mensaje_opciones
        )
        if not enviado_opciones:
            logger.warning(
                (
                    "⚠️ Se envió contexto de disponibilidad pero falló "
                    "mensaje de opciones para %s"
                ),
                telefono,
            )

    async def verificar_disponibilidad(
        self,
        *,
        req_id: str,
        servicio: str,
        ciudad: Optional[str],
        descripcion_problema: Optional[str],
        candidatos: List[Dict[str, Any]],
        cliente_redis: Any,
    ) -> Dict[str, Any]:
        """
        Verifica disponibilidad consultando por WhatsApp a cada proveedor.
        """
        req_id_real = f"{req_id}-{int(datetime.utcnow().timestamp() * 1000)}"
        logger.info(
            (
                "📍 Verificando disponibilidad: req_id=%s, "
                "servicio='%s', ciudad=%s, %s candidatos"
            ),
            req_id_real,
            servicio,
            ciudad or "N/A",
            len(candidatos),
        )

        ahora_iso = datetime.utcnow().isoformat()
        candidatos_por_telefono: Dict[str, Dict[str, Any]] = {}

        for candidato in candidatos:
            telefono = self._formatear_telefono_whatsapp(
                candidato.get("phone_number")
                or candidato.get("phone")
                or candidato.get("real_phone")
            )
            if not telefono:
                logger.warning(f"Proveedor sin teléfono válido: {candidato.get('id')}")
                continue
            item = dict(candidato)
            item["phone_jid"] = telefono
            item.setdefault("provider_id", item.get("id"))
            item.setdefault("nombre", item.get("name") or item.get("full_name"))
            candidatos_por_telefono[telefono] = item

        if not candidatos_por_telefono:
            logger.warning(
                "⚠️ No hay candidatos con teléfono para consultar disponibilidad"
            )
            return {"aceptados": [], "respondidos": [], "tiempo_agotado": False}

        # Publicar solicitudes pendientes y enviar WhatsApp
        # de forma concurrente controlada.
        tareas_envio = [
            self._registrar_y_enviar_a_proveedor(
                req_id_real=req_id_real,
                servicio=servicio,
                ciudad=ciudad,
                descripcion_problema=descripcion_problema,
                telefono=telefono,
                candidato=candidato,
                ahora_iso=ahora_iso,
                cliente_redis=cliente_redis,
            )
            for telefono, candidato in candidatos_por_telefono.items()
        ]
        await asyncio.gather(*tareas_envio, return_exceptions=True)

        aceptados: List[Dict[str, Any]] = []
        respondidos: List[Dict[str, Any]] = []
        pendientes_telefono = set(candidatos_por_telefono.keys())
        loop = asyncio.get_running_loop()
        fin_espera = loop.time() + self.timeout_seconds

        while pendientes_telefono and loop.time() < fin_espera:
            for telefono in list(pendientes_telefono):
                clave_solicitud = (
                    f"availability:request:{req_id_real}:provider:{telefono}"
                )
                estado = await cliente_redis.get(clave_solicitud)
                estado = self._decode_if_json_string(estado)
                if not isinstance(estado, dict):
                    # Puede ser una lectura transitoria; mantener pendiente hasta timeout.
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

        # Verificación final corta para absorber respuestas justo al borde del timeout.
        if pendientes_telefono and self.grace_seconds > 0:
            await asyncio.sleep(self.grace_seconds)
            for telefono in list(pendientes_telefono):
                clave_solicitud = f"availability:request:{req_id_real}:provider:{telefono}"
                estado = await cliente_redis.get(clave_solicitud)
                estado = self._decode_if_json_string(estado)
                if not isinstance(estado, dict):
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

        # Limpiar índices pendientes para este req_id
        for telefono in candidatos_por_telefono:
            clave_pendientes = f"availability:provider:{telefono}:pending"
            pendientes = await cliente_redis.get(clave_pendientes) or []
            pendientes = self._decode_if_json_string(pendientes)
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

    async def close(self) -> None:
        """Cerrar cliente HTTP compartido."""
        await self._client.aclose()


servicio_disponibilidad = ServicioDisponibilidad()
