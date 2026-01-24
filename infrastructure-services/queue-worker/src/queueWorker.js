/**
 * queueWorker.js
 * Worker principal que procesa mensajes de WhatsApp de la cola BullMQ
 *
 * Responsabilidad:
 * - Consumir jobs de la cola de webhooks
 * - Procesar mensajes con las capas de resiliencia (idempotency, locks)
 * - Publicar a MQTT topic ai-clientes/process para que ai-clientes procese
 * - Recibir respuestas vía MQTT (whatsapp/clientes/send)
 *
 * MQTT-First Architecture:
 * Flujo: WhatsApp → BullMQ → Worker → MQTT (ai-clientes/process) → ai-clientes
 *                                                    ↓
                                              MQTT (whatsapp/clientes/send)
 *                                                    ↓
                                      wa-clientes (Producer) → WhatsApp
 */

const { Worker } = require("bullmq");

// Importar configuraciones y servicios
const QueueConfig = require("../src/infrastructure/queue/QueueConfig");
const WebhookQueue = require("../src/infrastructure/queue/WebhookQueue");
const DistributedCache = require("../src/infrastructure/cache/DistributedCache");
const IdempotencyStore = require("../src/infrastructure/cache/IdempotencyStore");
const DistributedLock = require("../src/infrastructure/locking/DistributedLock");
const SessionLock = require("../src/infrastructure/locking/SessionLock");
const MqttAiPublisher = require("../src/infrastructure/messaging/MqttAiPublisher");
const MqttClient = require("../src/infrastructure/mqtt/MqttClient");
const config = require("../src/infrastructure/config/envConfig");
const timeouts = require("../src/infrastructure/config/timeouts");
const logger = require("./workerLogger");

// FASE 1: Función principal de inicio (usando async wrapper para CommonJS)
async function main() {
  // ============================================================================
  // SETUP DE SERVICIOS
  // ============================================================================

  logger.info("🚀 Iniciando Queue Worker de WhatsApp...");

  // 1. Inicializar Cache distribuido
  const distributedCache = new DistributedCache(
    process.env.REDIS_URL || "redis://localhost:6379",
    process.env.REDIS_PASSWORD,
  );
  await distributedCache.initialize();

  // 2. Inicializar Idempotency Store
  const idempotencyStore = new IdempotencyStore(distributedCache);

  // 3. Inicializar Distributed Lock
  const distributedLock = new DistributedLock(
    process.env.REDIS_URL || "redis://localhost:6379",
    process.env.REDIS_PASSWORD,
  );
  await distributedLock.initialize();

  // 4. Inicializar Session Lock
  const sessionLock = new SessionLock(distributedLock);

  // 5. Inicializar MQTT Client (para publicar a ai-clientes y recibir respuestas)
  // El Worker publica a ai-clientes/process y recibe respuestas en whatsapp/clientes/send
  const mqttClient = new MqttClient(config.mqtt, null); // null porque no envía directo
  mqttClient.connect({ autoSubscribe: true }); // Suscribirse para recibir respuestas

  // Esperar a que MQTT se conecte
  await new Promise((resolve) => {
    const checkInterval = setInterval(() => {
      if (mqttClient.isConnected()) {
        clearInterval(checkInterval);
        resolve();
      }
    }, 100);
  });

  logger.info("✅ MQTT Client conectado (modo publicación + suscripción)");

  // 6. Inicializar MqttAiPublisher (publica en ai-clientes/process)
  const aiPublisher = new MqttAiPublisher(mqttClient, {
    topic: process.env.MQTT_TEMA_AI_CLIENTES_PROCESS || 'ai-clientes/process',
    qos: 1,
  });

  logger.info("✅ Todos los servicios inicializados");

  // ============================================================================
  // PROCESSOR DE JOBS
  // ============================================================================

  /**
   * Procesa un job de la cola
   * @param {object} job - Job de BullMQ
   * @returns {Promise<void>}
   */
  async function processJob(job) {
    const startTime = Date.now();

    try {
      logger.logJobStart(job);

      // Extraer datos del mensaje
      const messageData = job.data.message;
      const phoneNumber = messageData.from;

      // ========================================================================
      // PASO 1: Verificar Idempotency
      // ========================================================================
      const messageKey = IdempotencyStore.generateMessageKey(messageData);
      const isFirstTime = await idempotencyStore.check(messageKey);

      if (!isFirstTime) {
        logger.logJobDuplicate(job);
        return; // Saltar procesamiento
      }

      // ========================================================================
      // PASO 2: Adquirir Session Lock
      // ========================================================================
      logger.logLockAttempt(phoneNumber, false);

      try {
        await sessionLock.runWithLock(
          phoneNumber,
          async () => {
            logger.logLockAttempt(phoneNumber, true);

          // ========================================================================
          // PASO 3: Publicar a MQTT para que ai-clientes procese
          // InputSanitizer ahora está en ai-clientes (Python)
          // ========================================================================

          // Publicar mensaje al topic ai-clientes/process
          // Si MQTT falla, el error se propaga y BullMQ hace retry
          await aiPublisher.publishMessage(messageData);
          logger.info(`📤 Mensaje publicado a ai-clientes/process para ${phoneNumber}`);

          logger.logJobComplete(job, Date.now() - startTime);
        },
        timeouts.SESSION_LOCK_TTL,
      );

      // ========================================================================
      // PASO 5: Cleanup
      // ========================================================================

      // El lock se libera automáticamente con runWithLock
      logger.logLockAttempt(phoneNumber, false); // Lock liberado
      } catch (lockErr) {
        // Si el lock falló, significa que otro job está procesando este mensaje
        // Retornar sin error para evitar retry de BullMQ
        if (lockErr.message.includes('No se pudo adquirir lock')) {
          logger.debug(`Job ${job.id} skip: lock no disponible para ${phoneNumber}`);
          return; // Skip sin lanzar error
        }
        // Si es otro error, relanzar
        throw lockErr;
      }
    } catch (err) {
      const duration = Date.now() - startTime;
      logger.logJobFailed(job, err, duration);

      // Relanzar error para que BullMQ haga el retry
      throw err;
    }
  }

  // ============================================================================
  // CREACIÓN DEL WORKER
  // ============================================================================

  logger.info("Creando Worker de BullMQ...");

  const workerOptions = {
    ...QueueConfig.defaultWorkerOptions,
    concurrency: parseInt(process.env.QUEUE_CONCURRENCY || "10", 10),
  };

  const worker = new Worker(
    QueueConfig.WEBHOOK_QUEUE_NAME,
    async (job) => {
      await processJob(job);
    },
    workerOptions,
  );

  // ============================================================================
  // EVENT HANDLERS DEL WORKER
  // ============================================================================

  worker.on("error", (err) => {
    logger.error("Worker error:", { error: err.message });
  });

  worker.on("ready", () => {
    logger.info("Worker listo para procesar jobs");
  });

  worker.on("active", (job) => {
    logger.debug("Job activo", { jobId: job.id });
  });

  worker.on("completed", (job) => {
    logger.logJobComplete(job, 0);
  });

  worker.on("failed", (job, err) => {
    logger.logJobFailed(job, err, 0);
  });

  worker.on("stalled", (jobId) => {
    logger.warn("Job stalled", { jobId });
  });

  worker.on("progress", (job, progress) => {
    logger.debug("Job progress", { jobId: job.id, progress });
  });

  // ============================================================================
  // GRACEFUL SHUTDOWN
  // ============================================================================

  async function shutdown() {
    logger.info("Iniciando shutdown del worker...");

    try {
      // Cerrar worker
      await worker.close();
      logger.info("Worker cerrado");

      // Cerrar MQTT client
      if (mqttClient && mqttClient.client && mqttClient.client.connected) {
        mqttClient.client.end();
        logger.info("MQTT client cerrado");
      }

      // Cerrar conexiones
      await distributedCache.close();
      await distributedLock.close();

      logger.info("✅ Worker shutdown completado");
      process.exit(0);
    } catch (err) {
      logger.error("Error durante shutdown:", { error: err.message });
      process.exit(1);
    }
  }

  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);

  // ============================================================================
  // INICIO
  // ============================================================================

  logger.info("✅ Worker iniciado y esperando jobs...");
  logger.info(`📊 Concurrency: ${workerOptions.concurrency}`);
  logger.info(`📦 Queue: ${QueueConfig.WEBHOOK_QUEUE_NAME}`);
  logger.info(`📡 MQTT: ${config.mqtt.host}:${config.mqtt.port}`);
  logger.info(`   → Publish: ai-clientes/process`);
  logger.info(`   ← Subscribe: ${config.mqtt.topicWhatsappSend}`);
}

// Iniciar el Worker
main().catch((error) => {
  console.error("Fatal error during worker startup:", error);
  console.error("Error stack:", error?.stack || "No stack trace");
  console.error("Error message:", error?.message || "No message");
  console.error("Error name:", error?.name || "No name");
  process.exit(1);
});
