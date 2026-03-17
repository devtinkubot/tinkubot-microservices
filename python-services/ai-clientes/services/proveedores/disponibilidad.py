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


CLAVE_CICLO_SOLICITUD = "availability:lifecycle:{}"
CLAVE_ALIAS_DISPONIBILIDAD = "availability:alias:{}"
AVAILABILITY_TEMPLATE_NAME = "provider_availability_request_v1"
AVAILABILITY_TEMPLATE_LANGUAGE = "es"
MENSAJE_SOLICITUD_CADUCADA = (
    "⏳ El tiempo para responder a esta solicitud *caducó* y ya no será considerada."
)


class ServicioDisponibilidad:
    """Servicio para verificar disponibilidad contactando proveedores."""

    def __init__(self) -> None:
        self.whatsapp_url = os.getenv("WHATSAPP_CLIENTES_URL", "http://wa-gateway:7000")
        self.account_id = os.getenv(
            "WHATSAPP_PROVEEDORES_ACCOUNT_ID", "bot-proveedores"
        )
        self.timeout_seconds = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "90"))
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
        ttl_lock_env = os.getenv("AVAILABILITY_PROVIDER_LOCK_TTL_SECONDS")
        ttl_lock_default = int(self.timeout_seconds + self.grace_seconds + 5)
        self.provider_lock_ttl_seconds = int(ttl_lock_env or ttl_lock_default)
        self._client = httpx.AsyncClient(
            timeout=self.send_timeout_seconds,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=100),
        )
        self._send_semaphore = asyncio.Semaphore(self.max_send_concurrency)
        if self.timeout_seconds < 30:
            logger.warning(
                "⚠️ AVAILABILITY_TIMEOUT_SECONDS bajo (%s). Verifica configuración.",
                self.timeout_seconds,
            )
        self._metricas: Dict[str, Any] = {
            "excluded_missing_real_phone_total": 0,
            "excluded_missing_real_phone_last_provider_ids": [],
        }

    @staticmethod
    def _decode_if_json_string(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    async def _actualizar_ciclo_solicitud(
        self,
        *,
        cliente_redis: Any,
        request_id: str,
        nuevo_estado: str,
        datos: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Actualiza el ciclo de vida de una solicitud de disponibilidad."""
        if not request_id:
            return
        clave = CLAVE_CICLO_SOLICITUD.format(request_id)
        actual = await cliente_redis.get(clave) or {}
        actual = self._decode_if_json_string(actual)
        if not isinstance(actual, dict):
            actual = {}

        actual.update(datos or {})
        actual["state"] = nuevo_estado
        actual["updated_at"] = datetime.utcnow().isoformat()
        await cliente_redis.set(clave, actual, expire=self.ttl_seconds)

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

    @staticmethod
    def _primer_nombre(nombre: str) -> str:
        partes = [parte.strip() for parte in str(nombre or "").split() if parte.strip()]
        return partes[0] if partes else "proveedor"

    @staticmethod
    def _normalizar_real_phone_a_jid(valor: Optional[str]) -> Optional[str]:
        if not valor:
            return None
        digitos = re.sub(r"\D", "", str(valor))
        if not digitos:
            return None
        return f"{digitos}@s.whatsapp.net"

    def _construir_aliases_proveedor(self, candidato: Dict[str, Any]) -> List[str]:
        aliases: List[str] = []
        for valor in (
            candidato.get("phone"),
            candidato.get("phone_number"),
            candidato.get("real_phone"),
        ):
            alias = self._formatear_telefono_whatsapp(valor)
            if alias and alias not in aliases:
                aliases.append(alias)
        return aliases

    def _resolver_destino_envio(
        self, candidato: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str], List[str]]:
        aliases = self._construir_aliases_proveedor(candidato)
        real_phone_jid = self._normalizar_real_phone_a_jid(candidato.get("real_phone"))
        if real_phone_jid:
            return real_phone_jid, "real_phone", aliases

        phone_jid = self._formatear_telefono_whatsapp(
            candidato.get("phone_number") or candidato.get("phone")
        )
        if phone_jid and not phone_jid.endswith("@lid"):
            return phone_jid, "jid_whatsapp", aliases
        if phone_jid and phone_jid.endswith("@lid"):
            return None, "missing_real_phone", aliases
        return None, None, aliases

    def obtener_metricas(self) -> Dict[str, Any]:
        return dict(self._metricas)

    def _registrar_exclusion_missing_real_phone(
        self, candidato: Dict[str, Any]
    ) -> None:
        self._metricas["excluded_missing_real_phone_total"] += 1
        provider_id = candidato.get("provider_id") or candidato.get("id")
        recientes = list(self._metricas["excluded_missing_real_phone_last_provider_ids"])
        if provider_id:
            recientes.append(provider_id)
        self._metricas["excluded_missing_real_phone_last_provider_ids"] = recientes[-20:]

    @staticmethod
    def _normalizar_necesidad(descripcion_problema: Optional[str], servicio: str) -> str:
        texto = re.sub(r"\s+", " ", str(descripcion_problema or "").strip())
        if not texto:
            return servicio

        texto = re.sub(
            r"^(?:qué|que)\s+alguien\s+",
            "",
            texto,
            flags=re.IGNORECASE,
        )
        texto = re.sub(
            r"^alguien\s+que\s+",
            "",
            texto,
            flags=re.IGNORECASE,
        )
        texto = re.sub(
            r"^(?:necesito|quiero|busco|requiero)\s+",
            "",
            texto,
            flags=re.IGNORECASE,
        )
        return texto.strip(" .") or servicio

    def _texto_timeout_disponibilidad(self) -> str:
        if self.timeout_seconds > 0 and self.timeout_seconds % 60 == 0:
            minutos = self.timeout_seconds // 60
            return f"{minutos} minuto" if minutos == 1 else f"{minutos} minutos"
        return f"{self.timeout_seconds} segundos"

    def _mensaje_disponibilidad_contexto(
        self,
        *,
        nombre: str,
        servicio: str,
        ciudad: Optional[str],
        descripcion_problema: Optional[str],
    ) -> str:
        ciudad_txt = ciudad or "tu ciudad"
        servicio_txt = re.sub(r"\s+", " ", str(servicio or "").strip()) or "el servicio solicitado"
        necesidad_txt = self._normalizar_necesidad(descripcion_problema, servicio_txt)
        return (
            f"*Oportunidad en {ciudad_txt}*\n\n"
            f"*Se requiere:* {servicio_txt}\n\n"
            f"*Necesidad del cliente:* {necesidad_txt}"
        )

    def _mensaje_disponibilidad_fallback(self) -> str:
        return (
            "Si no ves los botones, responde con una de estas opciones:\n\n"
            "*Disponible*\n"
            "*No disponible*\n\n"
            "Tienes 2 min para responder."
        )

    def _ui_disponibilidad(
        self,
        *,
        servicio: str,
        ciudad: Optional[str],
        descripcion_problema: Optional[str],
    ) -> Dict[str, Any]:
        ciudad_txt = re.sub(r"\s+", " ", str(ciudad or "").strip()) or "tu ciudad"
        servicio_txt = re.sub(r"\s+", " ", str(servicio or "").strip()) or "el servicio solicitado"
        necesidad_txt = self._normalizar_necesidad(descripcion_problema, servicio_txt)
        return {
            "type": "template",
            "template_name": AVAILABILITY_TEMPLATE_NAME,
            "template_language": AVAILABILITY_TEMPLATE_LANGUAGE,
            "template_components": [
                {
                    "type": "header",
                    "parameters": [
                        {"type": "text", "text": ciudad_txt},
                    ],
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": servicio_txt},
                        {"type": "text", "text": necesidad_txt},
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [
                        {"type": "payload", "payload": "availability_accept"}
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "1",
                    "parameters": [
                        {"type": "payload", "payload": "availability_reject"}
                    ],
                },
            ],
        }

    def _mensaje_disponibilidad_caducada(self) -> str:
        return MENSAJE_SOLICITUD_CADUCADA

    @staticmethod
    def _clave_lock_proveedor(telefono: str) -> str:
        return f"availability:provider:{telefono}:lock"

    async def _adquirir_lock_proveedor(
        self,
        *,
        cliente_redis: Any,
        telefono: str,
        request_id: str,
    ) -> bool:
        clave = self._clave_lock_proveedor(telefono)
        redis_raw = getattr(cliente_redis, "redis_client", None)
        if redis_raw is None:
            logger.warning(
                "⚠️ Lock atómico no disponible (redis_client ausente) provider=%s req_id=%s",
                telefono,
                request_id,
            )
            return False
        try:
            adquirido = await redis_raw.set(
                clave,
                request_id,
                nx=True,
                ex=self.provider_lock_ttl_seconds,
            )
            return bool(adquirido)
        except Exception as exc:
            logger.warning(
                "⚠️ Error adquiriendo lock atómico provider=%s req_id=%s: %s",
                telefono,
                request_id,
                exc,
            )
            return False

    async def _liberar_lock_proveedor(
        self,
        *,
        cliente_redis: Any,
        telefono: str,
        request_id: str,
    ) -> None:
        clave = self._clave_lock_proveedor(telefono)
        redis_raw = getattr(cliente_redis, "redis_client", None)
        if redis_raw is None:
            logger.warning(
                "⚠️ No se pudo liberar lock atómico (redis_client ausente) provider=%s req_id=%s",
                telefono,
                request_id,
            )
            return
        try:
            script = (
                "if redis.call('GET', KEYS[1]) == ARGV[1] then "
                "return redis.call('DEL', KEYS[1]) else return 0 end"
            )
            eliminado = await redis_raw.eval(script, 1, clave, request_id)
            if int(eliminado or 0) > 0:
                logger.info(
                    "availability_lock_released req_id=%s provider=%s",
                    request_id,
                    telefono,
                )
            else:
                logger.info(
                    (
                        "availability_lock_release_skipped_owner_mismatch "
                        "req_id=%s provider=%s"
                    ),
                    request_id,
                    telefono,
                )
        except Exception as exc:
            logger.warning(
                "⚠️ Error liberando lock atómico provider=%s req_id=%s: %s",
                telefono,
                request_id,
                exc,
            )

    async def _enviar_whatsapp(
        self,
        *,
        telefono: str,
        mensaje: str,
        ui: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            url = f"{self.whatsapp_url}/send"
            payload: Dict[str, Any] = {
                "account_id": self.account_id,
                "to": telefono,
                "message": mensaje,
            }
            if ui:
                payload["ui"] = ui
            if metadata:
                payload["metadata"] = metadata
            async with self._send_semaphore:
                respuesta = await self._client.post(
                    url,
                    json=payload,
                )
            if respuesta.status_code == 200:
                return True
            logger.warning(
                "⚠️ Error enviando disponibilidad a %s: status=%s metadata=%s body=%s",
                telefono,
                respuesta.status_code,
                metadata or {},
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
        telefono_envio: str,
        send_target_type: str,
        aliases: List[str],
        candidato: Dict[str, Any],
        ahora_iso: str,
        cliente_redis: Any,
    ) -> None:
        # phone canónico JID completo para correlación exacta solicitud-respuesta.
        clave_solicitud = f"availability:request:{req_id_real}:provider:{telefono}"
        clave_pendientes = f"availability:provider:{telefono}:pending"
        clave_contexto = f"availability:provider:{telefono}:context"

        solicitud = {
            "req_id": req_id_real,
            "provider_phone": telefono,
            "provider_id": candidato.get("provider_id"),
            "provider_name": candidato.get("nombre"),
            "service": servicio,
            "city": ciudad,
            "problem_description": (descripcion_problema or "").strip(),
            "send_target": telefono_envio,
            "send_target_type": send_target_type,
            "provider_phone_aliases": aliases,
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
        await cliente_redis.set(
            clave_contexto,
            {
                "expecting_response": True,
                "request_id": req_id_real,
                "provider_phone": telefono,
                "requested_at": ahora_iso,
                "service": servicio,
                "city": ciudad,
            },
            expire=self.ttl_seconds,
        )
        for alias in aliases:
            await cliente_redis.set(
                CLAVE_ALIAS_DISPONIBILIDAD.format(alias),
                {"provider_phone": telefono, "request_id": req_id_real},
                expire=self.ttl_seconds,
            )

        mensaje_contexto = self._mensaje_disponibilidad_contexto(
            nombre=str(candidato.get("nombre") or "").strip(),
            servicio=servicio,
            ciudad=ciudad,
            descripcion_problema=descripcion_problema,
        )
        logger.info(
            "availability_target_selected req_id=%s provider_id=%s send_target=%s send_target_type=%s correlation_phone=%s",
            req_id_real,
            candidato.get("provider_id"),
            telefono_envio,
            send_target_type,
            telefono,
        )
        enviado_contexto = await self._enviar_whatsapp(
            telefono=telefono_envio,
            mensaje=mensaje_contexto,
            ui=self._ui_disponibilidad(
                servicio=servicio,
                ciudad=ciudad,
                descripcion_problema=descripcion_problema,
            ),
            metadata={
                "source_service": "ai-clientes",
                "flow_type": "availability",
                "task_type": "provider_availability_request",
                "trace_id": req_id_real,
            },
        )
        if not enviado_contexto:
            mensaje_fallback = f"{mensaje_contexto}\n\n{self._mensaje_disponibilidad_fallback()}"
            enviado_fallback = await self._enviar_whatsapp(
                telefono=telefono_envio,
                mensaje=mensaje_fallback,
                metadata={
                    "source_service": "ai-clientes",
                    "flow_type": "availability",
                    "task_type": "provider_availability_request_fallback",
                    "trace_id": req_id_real,
                },
            )
            if enviado_fallback:
                return
            solicitud["status"] = "failed_to_send"
            await cliente_redis.set(clave_solicitud, solicitud, expire=self.ttl_seconds)
            return

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
        await self._actualizar_ciclo_solicitud(
            cliente_redis=cliente_redis,
            request_id=req_id_real,
            nuevo_estado="created",
            datos={
                "request_id": req_id_real,
                "service": servicio,
                "city": ciudad,
                "problem_description": (descripcion_problema or "").strip(),
                "created_at": datetime.utcnow().isoformat(),
            },
        )
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
        proveedores_ocupados: List[str] = []
        lock_busy_skip_count = 0
        excluded_missing_real_phone: List[str] = []

        for candidato in candidatos:
            telefono, send_target_type, aliases = self._resolver_destino_envio(candidato)
            if not telefono:
                if send_target_type == "missing_real_phone":
                    self._registrar_exclusion_missing_real_phone(candidato)
                    provider_id = str(candidato.get("provider_id") or candidato.get("id") or "")
                    if provider_id:
                        excluded_missing_real_phone.append(provider_id)
                    logger.info(
                        "availability_excluded_missing_real_phone provider_id=%s provider_phone=%s",
                        candidato.get("provider_id") or candidato.get("id"),
                        candidato.get("phone"),
                    )
                    continue
                logger.warning(f"Proveedor sin teléfono válido: {candidato.get('id')}")
                continue
            item = dict(candidato)
            item["phone_jid"] = telefono
            item["send_target"] = telefono
            item["send_target_type"] = send_target_type or "real_phone"
            item["phone_aliases"] = aliases or [telefono]
            item.setdefault("provider_id", item.get("id"))
            item.setdefault("nombre", item.get("name") or item.get("full_name"))
            candidatos_por_telefono[telefono] = item

        if not candidatos_por_telefono:
            logger.warning(
                "⚠️ No hay candidatos con teléfono para consultar disponibilidad"
            )
            await self._actualizar_ciclo_solicitud(
                cliente_redis=cliente_redis,
                request_id=req_id_real,
                nuevo_estado="closed",
                datos={
                    "close_reason": "no_candidates",
                    "candidates_total": 0,
                },
            )
            return {
                "aceptados": [],
                "respondidos": [],
                "tiempo_agotado": False,
                "request_id": req_id_real,
                "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
            }

        candidatos_disponibles: Dict[str, Dict[str, Any]] = {}
        locks_adquiridos: set[str] = set()
        for telefono, candidato in candidatos_por_telefono.items():
            lock_adquirido = await self._adquirir_lock_proveedor(
                cliente_redis=cliente_redis,
                telefono=telefono,
                request_id=req_id_real,
            )
            if not lock_adquirido:
                lock_busy_skip_count += 1
                proveedores_ocupados.append(telefono)
                logger.info(
                    (
                        "availability_lock_busy_skip req_id=%s "
                        "provider=%s lock_ttl_seconds=%s"
                    ),
                    req_id_real,
                    telefono,
                    self.provider_lock_ttl_seconds,
                )
                continue

            locks_adquiridos.add(telefono)
            logger.info(
                "availability_lock_acquired req_id=%s provider=%s lock_ttl_seconds=%s",
                req_id_real,
                telefono,
                self.provider_lock_ttl_seconds,
            )

            clave_pendientes = f"availability:provider:{telefono}:pending"
            pendientes = await cliente_redis.get(clave_pendientes) or []
            pendientes = self._decode_if_json_string(pendientes)
            if isinstance(pendientes, list) and pendientes:
                proveedores_ocupados.append(telefono)
                logger.info(
                    (
                        "availability_provider_excluded_busy req_id=%s "
                        "provider=%s pending_count=%s"
                    ),
                    req_id_real,
                    telefono,
                    len(pendientes),
                )
                await self._liberar_lock_proveedor(
                    cliente_redis=cliente_redis,
                    telefono=telefono,
                    request_id=req_id_real,
                )
                if telefono in locks_adquiridos:
                    locks_adquiridos.discard(telefono)
                continue
            candidatos_disponibles[telefono] = candidato

        await self._actualizar_ciclo_solicitud(
            cliente_redis=cliente_redis,
            request_id=req_id_real,
            nuevo_estado="candidates_found",
            datos={
                "candidates_total": len(candidatos_por_telefono),
                "candidate_phones": list(candidatos_por_telefono.keys()),
                "excluded_busy_providers_count": len(proveedores_ocupados),
                "excluded_busy_provider_phones": proveedores_ocupados,
                "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                "excluded_missing_real_phone_provider_ids": excluded_missing_real_phone,
                "candidates_available_count": len(candidatos_disponibles),
                "lock_busy_skip_count": lock_busy_skip_count,
                "lock_acquired_count": len(locks_adquiridos),
            },
        )

        if not candidatos_disponibles:
            logger.info(
                "availability_all_providers_busy req_id=%s excluded=%s",
                req_id_real,
                len(proveedores_ocupados),
            )
            await self._actualizar_ciclo_solicitud(
                cliente_redis=cliente_redis,
                request_id=req_id_real,
                nuevo_estado="closed",
                datos={
                    "close_reason": "all_providers_busy",
                    "timed_out": False,
                    "accepted_count": 0,
                    "responded_count": 0,
                    "lock_busy_skip_count": lock_busy_skip_count,
                    "lock_acquired_count": len(locks_adquiridos),
                },
            )
            return {
                "aceptados": [],
                "respondidos": [],
                "tiempo_agotado": False,
                "request_id": req_id_real,
                "excluded_busy_providers_count": len(proveedores_ocupados),
                "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                "lock_busy_skip_count": lock_busy_skip_count,
                "lock_acquired_count": len(locks_adquiridos),
            }

        try:
            # Publicar solicitudes pendientes y enviar WhatsApp
            # de forma concurrente controlada.
            tareas_envio = [
                self._registrar_y_enviar_a_proveedor(
                    req_id_real=req_id_real,
                    servicio=servicio,
                    ciudad=ciudad,
                    descripcion_problema=descripcion_problema,
                    telefono=telefono,
                    telefono_envio=str(candidato.get("send_target") or telefono),
                    send_target_type=str(
                        candidato.get("send_target_type") or "real_phone"
                    ),
                    aliases=list(candidato.get("phone_aliases") or [telefono]),
                    candidato=candidato,
                    ahora_iso=ahora_iso,
                    cliente_redis=cliente_redis,
                )
                for telefono, candidato in candidatos_disponibles.items()
            ]
            await asyncio.gather(*tareas_envio, return_exceptions=True)
            await self._actualizar_ciclo_solicitud(
                cliente_redis=cliente_redis,
                request_id=req_id_real,
                nuevo_estado="availability_pending",
                datos={
                    "pending_provider_count": len(candidatos_disponibles),
                },
            )

            aceptados: List[Dict[str, Any]] = []
            respondidos: List[Dict[str, Any]] = []
            pendientes_telefono = set(candidatos_disponibles.keys())
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
                        # Lectura transitoria: mantener pendiente hasta el timeout.
                        continue

                    status = str(estado.get("status") or "").strip().lower()
                    if status not in {"accepted", "rejected", "failed_to_send"}:
                        continue

                    candidato = candidatos_disponibles.get(telefono) or {}
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
                    clave_solicitud = (
                        f"availability:request:{req_id_real}:provider:{telefono}"
                    )
                    estado = await cliente_redis.get(clave_solicitud)
                    estado = self._decode_if_json_string(estado)
                    if not isinstance(estado, dict):
                        continue

                    status = str(estado.get("status") or "").strip().lower()
                    if status not in {"accepted", "rejected", "failed_to_send"}:
                        continue

                    candidato = candidatos_disponibles.get(telefono) or {}
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
            for telefono in candidatos_disponibles:
                clave_pendientes = f"availability:provider:{telefono}:pending"
                clave_contexto = f"availability:provider:{telefono}:context"
                pendientes = await cliente_redis.get(clave_pendientes) or []
                pendientes = self._decode_if_json_string(pendientes)
                if not isinstance(pendientes, list):
                    continue
                nuevos = [rid for rid in pendientes if rid != req_id_real]
                await cliente_redis.set(clave_pendientes, nuevos, expire=self.ttl_seconds)
                if not nuevos:
                    await cliente_redis.delete(clave_contexto)

            tiempo_agotado = bool(pendientes_telefono)
            if tiempo_agotado:
                logger.info(
                    "⏳ Disponibilidad timeout req_id=%s (pendientes=%s)",
                    req_id_real,
                    len(pendientes_telefono),
                )
                mensaje_caducado = self._mensaje_disponibilidad_caducada()
                for telefono in list(pendientes_telefono):
                    clave_solicitud = (
                        f"availability:request:{req_id_real}:provider:{telefono}"
                    )
                    estado = await cliente_redis.get(clave_solicitud)
                    estado = self._decode_if_json_string(estado)
                    if isinstance(estado, dict):
                        estado["status"] = "expired"
                        estado["expired_at"] = datetime.utcnow().isoformat()
                        await cliente_redis.set(
                            clave_solicitud, estado, expire=self.ttl_seconds
                        )

                    enviado_caducado = await self._enviar_whatsapp(
                        telefono=telefono,
                        mensaje=mensaje_caducado,
                        metadata={
                            "source_service": "ai-clientes",
                            "flow_type": "availability",
                            "task_type": "provider_availability_timeout",
                            "trace_id": req_id_real,
                        },
                    )
                    if enviado_caducado:
                        logger.info(
                            "availability_timeout_push_sent req_id=%s provider=%s service=%s city=%s timeout_seconds=%s",
                            req_id_real,
                            telefono,
                            servicio,
                            ciudad or "",
                            self.timeout_seconds,
                        )
                    else:
                        logger.warning(
                            "availability_timeout_push_failed req_id=%s provider=%s service=%s city=%s timeout_seconds=%s",
                            req_id_real,
                            telefono,
                            servicio,
                            ciudad or "",
                            self.timeout_seconds,
                        )

            if aceptados:
                await self._actualizar_ciclo_solicitud(
                    cliente_redis=cliente_redis,
                    request_id=req_id_real,
                    nuevo_estado="provider_accepted",
                    datos={
                        "accepted_count": len(aceptados),
                        "responded_count": len(respondidos),
                        "timed_out": tiempo_agotado,
                        "excluded_busy_providers_count": len(proveedores_ocupados),
                        "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                        "lock_busy_skip_count": lock_busy_skip_count,
                        "lock_acquired_count": len(locks_adquiridos),
                    },
                )
            elif respondidos:
                await self._actualizar_ciclo_solicitud(
                    cliente_redis=cliente_redis,
                    request_id=req_id_real,
                    nuevo_estado="provider_rejected",
                    datos={
                        "accepted_count": 0,
                        "responded_count": len(respondidos),
                        "timed_out": tiempo_agotado,
                        "excluded_busy_providers_count": len(proveedores_ocupados),
                        "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                        "lock_busy_skip_count": lock_busy_skip_count,
                        "lock_acquired_count": len(locks_adquiridos),
                    },
                )
            elif tiempo_agotado:
                await self._actualizar_ciclo_solicitud(
                    cliente_redis=cliente_redis,
                    request_id=req_id_real,
                    nuevo_estado="expired",
                    datos={
                        "accepted_count": 0,
                        "responded_count": 0,
                        "timed_out": True,
                        "excluded_busy_providers_count": len(proveedores_ocupados),
                        "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                        "lock_busy_skip_count": lock_busy_skip_count,
                        "lock_acquired_count": len(locks_adquiridos),
                    },
                )

            return {
                "aceptados": aceptados,
                "respondidos": respondidos,
                "tiempo_agotado": tiempo_agotado,
                "request_id": req_id_real,
                "excluded_busy_providers_count": len(proveedores_ocupados),
                "excluded_missing_real_phone_count": len(excluded_missing_real_phone),
                "lock_busy_skip_count": lock_busy_skip_count,
                "lock_acquired_count": len(locks_adquiridos),
            }
        finally:
            for telefono in locks_adquiridos:
                await self._liberar_lock_proveedor(
                    cliente_redis=cliente_redis,
                    telefono=telefono,
                    request_id=req_id_real,
                )

    async def marcar_solicitud_como_presentada(
        self,
        *,
        request_id: Optional[str],
        cliente_redis: Any,
        telefono_cliente: str,
        proveedores_presentados: int,
    ) -> None:
        """Marca que los proveedores se presentaron al cliente."""
        if not request_id:
            return
        await self._actualizar_ciclo_solicitud(
            cliente_redis=cliente_redis,
            request_id=request_id,
            nuevo_estado="presented_to_customer",
            datos={
                "customer_phone": telefono_cliente,
                "presented_providers_count": proveedores_presentados,
                "presented_at": datetime.utcnow().isoformat(),
            },
        )

    async def cerrar_solicitud(
        self,
        *,
        request_id: Optional[str],
        cliente_redis: Any,
        motivo: str,
    ) -> None:
        """Cierra formalmente la solicitud."""
        if not request_id:
            return
        await self._actualizar_ciclo_solicitud(
            cliente_redis=cliente_redis,
            request_id=request_id,
            nuevo_estado="closed",
            datos={
                "close_reason": motivo,
                "closed_at": datetime.utcnow().isoformat(),
            },
        )

    async def start_listener(self) -> None:
        """Compatibilidad con la interfaz anterior."""
        return None

    async def close(self) -> None:
        """Cerrar cliente HTTP compartido."""
        await self._client.aclose()


servicio_disponibilidad = ServicioDisponibilidad()
