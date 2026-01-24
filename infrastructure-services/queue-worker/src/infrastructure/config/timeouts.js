/**
 * timeouts.js
 * Configuración centralizada de timeouts para el servicio
 *
 * Responsabilidad:
 * - Centralizar todos los timeouts del sistema
 * - Proveer valores consistentes para todos los componentes
 * - Facilitar ajustes de performance en un solo lugar
 *
 * Fase 1: Estabilización Crítica
 * Valores basados en percentiles reales de OpenAI y análisis de carga
 */

module.exports = {
  // ==========================================
  // AI SERVICE TIMEOUTS
  // ==========================================
  // OpenAI response time p95: ~8 segundos
  // Con overhead de red y procesamiento: 15s es seguro
  OPENAI_TIMEOUT: parseInt(process.env.OPENAI_TIMEOUT_MS || '15000', 10),

  // Timeout para llamadas al AI Service desde wa-clientes
  // Debe ser mayor que OPENAI_TIMEOUT para no cortar respuestas válidas
  AI_SERVICE_TIMEOUT: parseInt(process.env.AI_SERVICE_TIMEOUT_MS || '25000', 10),

  // ==========================================
  // WHATSAPP WEBHOOK TIMEOUTS
  // ==========================================
  // Timeout para enquear mensajes (NO procesamiento)
  // Este es solo el tiempo para agregar a BullMQ, debe ser <100ms
  WHATSAPP_WEBHOOK_ENQUEUE: 500,

  // ==========================================
  // CIRCUIT BREAKER TIMEOUTS
  // ==========================================
  // Tiempo máximo para esperar respuesta antes de abrir el circuito
  CIRCUIT_BREAKER_TIMEOUT: parseInt(process.env.CIRCUIT_BREAKER_TIMEOUT_MS || '30000', 10),

  // Tiempo para esperar antes de intentar cerrar el circuito (half-open)
  CIRCUIT_RESET_TIMEOUT: parseInt(process.env.CIRCUIT_RESET_TIMEOUT_MS || '60000', 10),

  // ==========================================
  // LOCK TIMEOUTS
  // ==========================================
  // TTL para locks de sesión por usuario
  // Previene deadlocks si un proceso falla
  SESSION_LOCK_TTL: parseInt(process.env.SESSION_LOCK_TTL_MS || '30000', 10),

  // ==========================================
  // IDEMPOTENCY TIMEOUTS
  // ==========================================
  // TTL para claves de idempotencia en Redis
  // 5 minutos es suficiente para prevenir duplicados de WhatsApp retries
  IDEMPOTENCY_TTL: parseInt(process.env.IDEMPOTENCY_TTL_SECONDS || '300', 10),

  // ==========================================
  // MQTT TIMEOUTS (MOSQUITTO INTACTO)
  // ==========================================
  // Timeout para esperar respuestas de proveedores via MQTT
  // Este valor NO se modifica en Fase 1 (Mosquitto permanece intacto)
  MQTT_AVAILABILITY_TIMEOUT: 45000,

  // ==========================================
  // QUEUE TIMEOUTS
  // ==========================================
  // TTL para jobs en cola antes de ser marcados como expirados
  QUEUE_JOB_TTL: parseInt(process.env.QUEUE_JOB_TTL || '300000', 10), // 5 minutos

  // Tiempo máximo para reintentar jobs fallidos
  QUEUE_RETRY_DELAY: 2000,

  // ==========================================
  // RETRY TIMEOUTS
  // ==========================================
  // Delay base para reintentos exponenciales
  RETRY_BASE_DELAY: 300,

  // Factor de multiplicación para backoff exponencial
  RETRY_MULTIPLIER: 2,

  // Número máximo de reintentos
  RETRY_MAX_ATTEMPTS: parseInt(process.env.QUEUE_MAX_RETRIES || '3', 10),
};
