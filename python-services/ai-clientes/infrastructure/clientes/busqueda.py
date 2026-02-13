"""
Cliente HTTP para comunicarse con Search Service
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

from config.configuracion import configuracion

logger = logging.getLogger(__name__)


class ClienteBusqueda:
    """Cliente para Search Service"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or f"http://ai-search:{configuracion.ai_search_port}"
        self.internal_token = os.getenv("AI_SEARCH_INTERNAL_TOKEN", "")
        self.timeout = float(os.getenv("SEARCH_HTTP_TIMEOUT_SECONDS", "10"))
        self.pool_timeout = float(os.getenv("SEARCH_POOL_TIMEOUT_SECONDS", "2"))
        max_connections = int(os.getenv("SEARCH_HTTP_MAX_CONNECTIONS", "200"))
        max_keepalive = int(os.getenv("SEARCH_HTTP_MAX_KEEPALIVE", "100"))

        self.max_inflight = int(os.getenv("SEARCH_MAX_INFLIGHT", "60"))
        self.max_queue = int(os.getenv("SEARCH_MAX_QUEUE", "80"))
        self._inflight_semaphore = asyncio.Semaphore(self.max_inflight)
        self._queue_lock = asyncio.Lock()
        self._queued_waiters = 0

        self.cb_failure_threshold = int(os.getenv("SEARCH_CB_FAILURE_THRESHOLD", "5"))
        self.cb_open_seconds = float(os.getenv("SEARCH_CB_OPEN_SECONDS", "20"))
        self.cb_half_open_success_threshold = int(
            os.getenv("SEARCH_CB_HALF_OPEN_SUCCESS_THRESHOLD", "2")
        )
        self._cb_state = "closed"
        self._cb_failure_count = 0
        self._cb_half_open_success_count = 0
        self._cb_open_until = 0.0
        self._cb_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=self.timeout,
                connect=self.timeout,
                read=self.timeout,
                write=self.timeout,
                pool=self.pool_timeout,
            ),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive,
            ),
        )

    async def buscar_proveedores(
        self,
        consulta: str,
        ciudad: Optional[str] = None,
        descripcion_problema: Optional[str] = None,
        service_candidate: Optional[str] = None,
        limite: int = 10,
    ) -> Dict[str, Any]:
        """
        Buscar proveedores en Search Service

        Args:
            consulta: Texto de búsqueda
            ciudad: Ciudad para filtrar
            descripcion_problema: Contexto original del usuario (trazabilidad)
            service_candidate: Servicio detectado por IA para contexto adicional
            limite: Límite de resultados
        Returns:
            Dict con resultados de búsqueda
        """
        slot_adquirido = False
        try:
            if not self.internal_token:
                logger.error("❌ AI_SEARCH_INTERNAL_TOKEN no configurado en ai-clientes")
                return self._crear_respuesta_error(
                    "Token interno de búsqueda no configurado",
                    degrade_reason="internal_token_missing",
                )

            if not await self._circuit_breaker_permite_trafico():
                return self._crear_respuesta_error(
                    "Servicio de búsqueda temporalmente saturado",
                    degrade_reason="breaker_open",
                )

            slot_adquirido = await self._adquirir_slot_busqueda()
            if not slot_adquirido:
                return self._crear_respuesta_error(
                    "Sistema temporalmente ocupado, intenta en unos segundos",
                    degrade_reason="queue_full",
                )

            carga = {
                "query": consulta,
                "limit": limite,
            }
            context_payload: Dict[str, Any] = {}
            if descripcion_problema:
                context_payload["problem_description"] = descripcion_problema
            if service_candidate:
                context_payload["service_candidate"] = service_candidate
            if context_payload:
                context_payload["language_hint"] = "es"
                carga["context"] = context_payload

            # Agregar filtros si se proporcionan
            filtros: Dict[str, Any] = {"verified_only": True}
            if ciudad:
                filtros["city"] = ciudad.lower()  # Normalizar a minúsculas para case-insensitive

            carga["filters"] = filtros

            respuesta = await self._client.post(
                f"{self.base_url}/api/v1/search",
                json=carga,
                headers={"X-Internal-Token": self.internal_token},
            )
            respuesta.raise_for_status()

            resultado = respuesta.json()
            await self._registrar_exito_busqueda()
            logger.info(
                f"✅ Búsqueda en Search Service: {len(resultado.get('providers', []))} resultados "
                f"(estrategia: {resultado.get('metadata', {}).get('search_strategy', 'unknown')})"
            )

            return self._convertir_resultado_busqueda_a_formato_legacy(resultado)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status >= 500 or status == 429:
                await self._registrar_fallo_busqueda(f"http_{status}")
            logger.error(
                f"❌ Error HTTP en Search Service: {e.response.status_code} - {e.response.text}"
            )
            return self._crear_respuesta_error(
                f"Error HTTP {e.response.status_code}",
                degrade_reason="upstream_http_error",
            )

        except httpx.TimeoutException:
            await self._registrar_fallo_busqueda("timeout")
            logger.error("⏰ Timeout en Search Service")
            return self._crear_respuesta_error(
                "Timeout en Search Service", degrade_reason="upstream_timeout"
            )

        except httpx.HTTPError as exc:
            await self._registrar_fallo_busqueda("http_client_error")
            logger.error(f"❌ Error HTTP de cliente hacia Search Service: {exc}")
            return self._crear_respuesta_error(
                "Error de conexión con Search Service",
                degrade_reason="upstream_connection_error",
            )

        except Exception as exc:
            logger.error(f"❌ Error comunicándose con Search Service: {exc}")
            return self._crear_respuesta_error(
                str(exc), degrade_reason="unexpected_error"
            )
        finally:
            if slot_adquirido:
                self._inflight_semaphore.release()

    def _convertir_resultado_busqueda_a_formato_legacy(
        self, resultado_busqueda: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convertir formato del Search Service al formato legado que espera ai-service-clientes
        """
        proveedores = resultado_busqueda.get("providers", [])
        metadatos = resultado_busqueda.get("metadata", {})

        # Convertir proveedores al formato legado
        proveedores_legacy = []
        for proveedor in proveedores:
            proveedor_legacy = {
                "id": proveedor.get("id"),
                "phone_number": proveedor.get("phone_number"),
                "real_phone": proveedor.get("real_phone") or proveedor.get("phone_number"),
                "full_name": proveedor.get("full_name"),
                "name": proveedor.get("full_name"),
                "city": proveedor.get("city"),
                "rating": proveedor.get("rating", 0.0),
                "available": proveedor.get("available", True),
                "verified": proveedor.get("verified", False),
                "professions": proveedor.get("professions", []),
                "services": proveedor.get("services", []),
                "years_of_experience": proveedor.get("years_of_experience"),
                "created_at": proveedor.get("created_at"),
                "social_media_url": proveedor.get("social_media_url"),
                "social_media_type": proveedor.get("social_media_type"),
                "face_photo_url": proveedor.get("face_photo_url"),
                # Calcular score basado en rating y disponibilidad
                "score": self._calcular_puntaje_legacy(proveedor),
            }
            proveedores_legacy.append(proveedor_legacy)

        return {
            "ok": True,
            "providers": proveedores_legacy,
            "total": len(proveedores_legacy),
            "search_metadata": {
                "strategy": metadatos.get("search_strategy"),
                "search_time_ms": metadatos.get("search_time_ms"),
                "confidence": metadatos.get("confidence"),
                "used_embeddings": metadatos.get("used_embeddings", True),
                "cache_hit": metadatos.get("cache_hit", False),
                "degraded": metadatos.get("degraded", False),
                "degrade_reason": metadatos.get("degrade_reason"),
            },
        }

    def _calcular_puntaje_legacy(self, proveedor: Dict[str, Any]) -> float:
        """
        Calcular score legado basado en rating y otros factores
        """
        calificacion = proveedor.get("rating", 0.0)
        disponible = proveedor.get("available", True)
        verificado = proveedor.get("verified", False)

        # Base: rating normalizado a 0-100
        puntaje = (calificacion / 5.0) * 100

        # Bonificaciones
        if disponible:
            puntaje += 20
        if verificado:
            puntaje += 10

        return min(100.0, puntaje)

    def _crear_respuesta_error(
        self, mensaje_error: str, degrade_reason: str = "unknown_error"
    ) -> Dict[str, Any]:
        """
        Crear respuesta de error en formato legado
        """
        return {
            "ok": False,
            "providers": [],
            "total": 0,
            "error": mensaje_error,
            "search_metadata": {
                "strategy": "error",
                "search_time_ms": 0,
                "confidence": 0.0,
                "used_embeddings": False,
                "cache_hit": False,
                "degraded": True,
                "degrade_reason": degrade_reason,
            },
        }

    async def _adquirir_slot_busqueda(self) -> bool:
        async with self._queue_lock:
            if self._queued_waiters >= self.max_queue:
                logger.warning(
                    "⚠️ Backpressure activado: cola llena para ai-search",
                    extra={
                        "max_queue": self.max_queue,
                        "queued_waiters": self._queued_waiters,
                        "max_inflight": self.max_inflight,
                    },
                )
                return False
            self._queued_waiters += 1

        try:
            await self._inflight_semaphore.acquire()
            return True
        finally:
            async with self._queue_lock:
                self._queued_waiters -= 1

    async def _circuit_breaker_permite_trafico(self) -> bool:
        async with self._cb_lock:
            if self._cb_state != "open":
                return True

            now = time.monotonic()
            if now < self._cb_open_until:
                return False

            self._cb_state = "half_open"
            self._cb_half_open_success_count = 0
            logger.info("🔄 Circuit breaker ai-search: transición OPEN -> HALF_OPEN")
            return True

    async def _registrar_exito_busqueda(self) -> None:
        async with self._cb_lock:
            if self._cb_state == "half_open":
                self._cb_half_open_success_count += 1
                if (
                    self._cb_half_open_success_count
                    >= self.cb_half_open_success_threshold
                ):
                    self._cb_state = "closed"
                    self._cb_failure_count = 0
                    self._cb_half_open_success_count = 0
                    logger.info(
                        "✅ Circuit breaker ai-search: transición HALF_OPEN -> CLOSED"
                    )
                return

            if self._cb_state == "closed":
                self._cb_failure_count = 0

    async def _registrar_fallo_busqueda(self, motivo: str) -> None:
        async with self._cb_lock:
            if self._cb_state == "half_open":
                self._abrir_circuit_breaker_locked(motivo)
                return

            if self._cb_state == "closed":
                self._cb_failure_count += 1
                if self._cb_failure_count >= self.cb_failure_threshold:
                    self._abrir_circuit_breaker_locked(motivo)

    def _abrir_circuit_breaker_locked(self, motivo: str) -> None:
        self._cb_state = "open"
        self._cb_open_until = time.monotonic() + self.cb_open_seconds
        self._cb_failure_count = 0
        self._cb_half_open_success_count = 0
        logger.warning(
            "🚨 Circuit breaker ai-search: transición a OPEN",
            extra={
                "reason": motivo,
                "open_seconds": self.cb_open_seconds,
                "failure_threshold": self.cb_failure_threshold,
            },
        )

    async def close(self) -> None:
        """Cerrar cliente HTTP compartido."""
        await self._client.aclose()


# Instancia global del cliente
cliente_busqueda = ClienteBusqueda()
