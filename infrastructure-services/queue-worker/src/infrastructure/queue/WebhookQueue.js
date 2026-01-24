/**
 * WebhookQueue.js
 * Wrapper específico para la cola de webhooks de WhatsApp
 *
 * Responsabilidad:
 * - Proporcionar métodos específicos para enqueue de webhooks
 * - Abstraer la complejidad de BullMQ
 * - Validar y normalizar datos de webhooks antes de enqueue
 *
 * Fase 1: Estabilización Crítica
 */

const QueueFactory = require('./QueueFactory');
const QueueConfig = require('./QueueConfig');
const timeouts = require('../config/timeouts');

class WebhookQueue {
  constructor() {
    this._queue = null;
  }

  /**
   * Inicializa la cola de webhooks
   * @returns {WebhookQueue} this (fluent interface)
   */
  initialize() {
    if (this._queue) {
      console.warn('[WebhookQueue] Ya inicializada, retornando instancia existente');
      return this;
    }

    console.info('[WebhookQueue] Inicializando cola de webhooks...');
    this._queue = QueueFactory.createQueue(QueueConfig.WEBHOOK_QUEUE_NAME);
    console.info('[WebhookQueue] Cola de webhooks inicializada');
    return this;
  }

  /**
   * Agrega un mensaje de WhatsApp a la cola
   * @param {object} messageData - Datos del mensaje de WhatsApp
   * @param {object} options - Opciones adicionales para el job
   * @returns {Promise<Job>} Job creado en BullMQ
   */
  async enqueue(messageData, options = {}) {
    if (!this._queue) {
      throw new Error('[WebhookQueue] Cola no inicializada. Llamar a initialize() primero.');
    }

    const jobId = this._generateJobId(messageData);

    const jobOptions = {
      jobId,
      // Opciones por defecto
      attempts: timeouts.RETRY_MAX_ATTEMPTS,
      timeout: timeouts.QUEUE_JOB_TTL,
      // Sobrescribir con opciones del usuario
      ...options,
    };

    const jobData = {
      message: messageData,
      enqueuedAt: new Date().toISOString(),
      enqueuedAtTimestamp: Date.now(),
    };

    try {
      const job = await this._queue.add('process-webhook', jobData, jobOptions);
      console.debug(`[WebhookQueue] Job ${job.id} enqueued para ${messageData.from}`);
      return job;
    } catch (err) {
      console.error(`[WebhookQueue] Error enqueueando mensaje:`, err.message);
      throw err;
    }
  }

  /**
   * Genera un ID único para el job basado en el mensaje
   * Previene duplicados usando el ID del mensaje de WhatsApp
   * @private
   * @param {object} messageData - Datos del mensaje
   * @returns {string} ID único para el job
   */
  _generateJobId(messageData) {
    // Usar el ID del mensaje de WhatsApp como jobId
    // Esto previene que el mismo mensaje se encolé múltiples veces
    const messageId = messageData.id?._serialized || messageData.id || 'unknown';
    // BullMQ no permite ":" en los job IDs, usamos "-"
    const safeMessageId = messageId.replace(/:/g, '-');
    return `whatsapp-${safeMessageId}`;
  }

  /**
   * Crea un Worker para procesar jobs de esta cola
   * @param {function} processor - Función procesadora de jobs
   * @param {object} options - Opciones adicionales para el worker
   * @returns {Worker} Instancia de Worker de BullMQ
   */
  createWorker(processor, options = {}) {
    const { Worker } = require('bullmq');

    const mergedOptions = {
      ...QueueConfig.defaultWorkerOptions,
      ...options,
    };

    const worker = new Worker(
      QueueConfig.WEBHOOK_QUEUE_NAME,
      processor,
      mergedOptions
    );

    this._setupWorkerEventHandlers(worker);

    return worker;
  }

  /**
   * Configura event handlers para un worker
   * @private
   * @param {Worker} worker - Instancia de Worker
   */
  _setupWorkerEventHandlers(worker) {
    worker.on('error', (err) => {
      console.error('[WebhookQueue:Worker] Error:', err.message);
    });

    worker.on('stalled', (jobId) => {
      console.warn(`[WebhookQueue:Worker] Job ${jobId} stalled`);
    });

    worker.on('completed', (job) => {
      console.debug(`[WebhookQueue:Worker] Job ${job.id} completado`);
    });

    worker.on('failed', (job, err) => {
      console.error(`[WebhookQueue:Worker] Job ${job?.id} falló:`, err.message);
    });
  }

  /**
   * Obtiene estadísticas de la cola
   * @returns {Promise<object>} Estadísticas
   */
  async getStats() {
    if (!this._queue) {
      throw new Error('[WebhookQueue] Cola no inicializada');
    }

    return QueueFactory.getQueueStats(QueueConfig.WEBHOOK_QUEUE_NAME);
  }

  /**
   * Limpia jobs completados y fallidos antiguos
   * @param {number} age - Edad máxima en segundos (default: 24 horas)
   * @returns {Promise<void>}
   */
  async cleanOldJobs(age = 86400) {
    if (!this._queue) {
      throw new Error('[WebhookQueue] Cola no inicializada');
    }

    console.info(`[WebhookQueue] Limpiando jobs antiguos (> ${age}s)...`);

    await this._queue.clean(age, 1000, 'completed');
    await this._queue.clean(age, 5000, 'failed');

    console.info('[WebhookQueue] Limpieza completada');
  }

  /**
   * Cierra la cola y libera recursos
   * @returns {Promise<void>}
   */
  async close() {
    if (this._queue) {
      await this._queue.close();
      this._queue = null;
      console.info('[WebhookQueue] Cola cerrada');
    }
  }

  /**
   * Obtiene la instancia de cola subyacente
   * @returns {Queue} Instancia de BullMQ Queue
   */
  getQueue() {
    return this._queue;
  }
}

// Exportar clase (no singleton, se puede crear múltiples instancias si es necesario)
module.exports = WebhookQueue;
