"""
Provider Synonym Optimizer - Escucha aprobaciones de proveedores y genera sinónimos.

Este servicio se suscribe a eventos MQTT de aprobación de proveedores
y genera automáticamente sinónimos para optimizar búsquedas futuras.

FEATURE FLAG: USE_AUTO_SYNONYM_GENERATION (default: false)

Estrategia Anti-Breaking Changes:
- Sistema desactivado por defecto
- No falla el startup si hay errores
- Logs claros de estado
- Listener MQTT en segundo plano
"""
import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

try:
    from asyncio_mqtt import Client as MQTTClient, MqttError
except ImportError:
    MQTTClient = None  # type: ignore
    MqttError = Exception

logger = logging.getLogger(__name__)

# Configuración MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USUARIO = os.getenv("MQTT_USUARIO", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))


class ProviderSynonymOptimizer:
    """
    Optimizador de sinónimos que escucha aprobaciones de proveedores.

    Responsabilidades:
    - Crear listener MQTT para el tópico providers/approved
    - Recibir eventos cuando se aprueba un proveedor
    - Delegar generación de sinónimos a AutoProfessionGenerator
    - Manejar errores gracefulmente (no romper el servicio)

    Anti-Breaking:
    - Si falla MQTT, solo loguea error
    - Si falla la generación, no afecta la aprobación
    - Feature flag controla todo el flujo
    """

    def __init__(
        self,
        auto_profession_generator: Any,
        enabled: bool = False
    ):
        """
        Inicializa el optimizador de sinónimos.

        Args:
            auto_profession_generator: Generador de sinónimos
            enabled: Si está activo (feature flag)
        """
        self.generator = auto_profession_generator
        self.enabled = enabled
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

        if self.enabled:
            logger.info("✅ ProviderSynonymOptimizer inicializado (ACTIVO)")
        else:
            logger.info("⏸️ ProviderSynonymOptimizer inicializado (INACTIVO - feature flag)")

    def _client_params(self) -> Dict[str, Any]:
        """Retorna parámetros para conectar al broker MQTT."""
        params: Dict[str, Any] = {
            "hostname": MQTT_HOST,
            "port": MQTT_PORT,
        }

        if MQTT_USUARIO and MQTT_PASSWORD:
            params["username"] = MQTT_USUARIO
            params["password"] = MQTT_PASSWORD

        return params

    async def start(self) -> bool:
        """
        Inicia el optimizador creando un listener MQTT en segundo plano.

        Returns:
            True si se inició correctamente, False en caso contrario
        """
        if not self.enabled:
            logger.info("⏸️ ProviderSynonymOptimizer NO iniciado (feature flag desactivado)")
            return False

        if not MQTTClient:
            logger.error(
                "❌ asyncio-mqtt no está instalado. "
                "ProviderSynonymOptimizer no puede iniciar."
            )
            return False

        try:
            # Crear tarea en segundo plano para el listener MQTT
            self._running = True
            self._listener_task = asyncio.create_task(self._mqtt_listener_loop())
            logger.info("📡 ProviderSynonymOptimizer listener iniciado (tópico: providers/approved)")
            return True

        except Exception as e:
            logger.error(
                f"❌ Error al iniciar ProviderSynonymOptimizer: {e}. "
                "Continuando sin optimización automática."
            )
            self._running = False
            return False

    async def _mqtt_listener_loop(self) -> None:
        """
        Loop de escucha de mensajes MQTT.

        Sigue el patrón de asyncio-mqtt:
        - Conectar al broker
        - Suscribirse al tópico
        - Escuchar mensajes en un loop
        - Reconectarse si se desconecta
        """
        while self._running:
            try:
                logger.info("🔧 [ProviderSynonymOptimizer] Conectando a MQTT broker...")

                async with MQTTClient(**self._client_params()) as client:
                    # Suscribirse al tópico providers/approved
                    topic = "providers/approved"
                    await client.subscribe(topic, qos=MQTT_QOS)
                    logger.info(f"📡 [ProviderSynonymOptimizer] Suscrito a tópico: {topic}")

                    # Escuchar mensajes
                    async with client.filtered_messages(topic) as messages:
                        logger.info("🔧 [ProviderSynonymOptimizer] Esperando eventos de aprobación...")
                        async for message in messages:
                            try:
                                # Decodificar payload
                                payload_str = message.payload.decode()
                                payload = json.loads(payload_str)

                                # Manejar evento
                                await self._handle_provider_approved(payload)

                            except json.JSONDecodeError as e:
                                logger.warning(f"⚠️ Error decodificando JSON: {e}")
                            except Exception as e:
                                logger.error(f"❌ Error procesando mensaje MQTT: {e}")

            except MqttError as e:
                logger.error(f"❌ Error MQTT: {e}")
                if self._running:
                    # Esperar antes de reconectar
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("📡 [ProviderSynonymOptimizer] Listener cancelado")
                break
            except Exception as e:
                logger.error(f"❌ Error inesperado en listener loop: {e}")
                if self._running:
                    await asyncio.sleep(5)

    async def _handle_provider_approved(self, payload: Dict[str, Any]) -> None:
        """
        Maneja evento de proveedor aprobado.

        Args:
            payload: Diccionario con provider_id, profession, city, etc.
        """
        if not self.enabled:
            return

        try:
            # Extraer datos del payload
            provider_id = payload.get("provider_id")
            profession = payload.get("profession")
            city = payload.get("city")
            specialty = payload.get("specialty")

            if not profession:
                logger.warning(
                    f"⚠️ Evento providers/approved sin campo 'profession'. "
                    f"Payload: {payload}"
                )
                return

            logger.info(
                f"🎯 [ProviderSynonymOptimizer] Proveedor aprobado: {profession} "
                f"(ID: {provider_id}, Ciudad: {city})"
            )

            # Generar sinónimos
            result = await self.generator.generate_for_profession(
                profession=profession,
                provider_id=provider_id,
                city=city,
                specialty=specialty
            )

            if result.get("status") == "created":
                logger.info(
                    f"✅ [ProviderSynonymOptimizer] Sinónimos generados: "
                    f"{result.get('synonyms_count', 0)} para '{profession}'"
                )
            elif result.get("status") == "already_exists":
                logger.info(
                    f"ℹ️ [ProviderSynonymOptimizer] Profesión '{profession}' ya tenía sinónimos. "
                    f"Skipping ({result.get('count', 0)} existentes)"
                )
            else:
                logger.warning(
                    f"⚠️ [ProviderSynonymOptimizer] Resultado inesperado: {result}"
                )

        except Exception as e:
            logger.error(
                f"❌ [ProviderSynonymOptimizer] Error manejando evento: {e}. "
                "No se afectará la aprobación del proveedor."
            )

    async def stop(self) -> None:
        """Detiene el optimizador (para shutdown)."""
        self._running = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                logger.info("📡 [ProviderSynonymOptimizer] Listener detenido")
            except Exception as e:
                logger.warning(f"⚠️ Error deteniendo listener: {e}")

        logger.info("📡 [ProviderSynonymOptimizer] Detenido")
