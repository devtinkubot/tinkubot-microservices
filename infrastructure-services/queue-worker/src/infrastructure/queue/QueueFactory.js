/**
 * QueueFactory.js
 * Factory para crear instancias de colas BullMQ
 *
 * Responsabilidad:
 * - Crear colas BullMQ con configuración optimizada
 * - Implementar Singleton pattern para reutilizar conexiones
 * - Centralizar la creación de colas y workers
 *
 * Fase 1: Estabilización Crítica
 */

const { Queue } = require('bullmq');
const QueueConfig = require('./QueueConfig');

class QueueFactory {
  constructor() {
    this._queues = new Map();
    this._connection = null;
  }

  /**
   * Obtiene o crea la conexión a Redis
   * @returns {Redis} Conexión a Redis
   */
  _getConnection() {
    if (!this._connection) {
      this._connection = QueueConfig.createRedisConnection();
    }
    return this._connection;
  }

  /**
   * Crea una nueva cola BullMQ
   * @param {string} queueName - Nombre de la cola
   * @param {object} options - Opciones adicionales para la cola
   * @returns {Queue} Instancia de cola BullMQ
   */
  createQueue(queueName, options = {}) {
    // Si ya existe, retornar la instancia existente
    if (this._queues.has(queueName)) {
      console.debug(`[QueueFactory] Retornando cola existente: ${queueName}`);
      return this._queues.get(queueName);
    }

    console.info(`[QueueFactory] Creando nueva cola: ${queueName}`);

    const mergedOptions = {
      ...QueueConfig.defaultQueueOptions,
      ...options,
    };

    const queue = new Queue(queueName, mergedOptions);

    // Guardar referencia para reutilizar
    this._queues.set(queueName, queue);

    // Event handlers para monitoreo
    this._setupQueueEventHandlers(queue, queueName);

    return queue;
  }

  /**
   * Configura event handlers para una cola
   * @private
   * @param {Queue} queue - Instancia de cola
   * @param {string} queueName - Nombre de la cola
   */
  _setupQueueEventHandlers(queue, queueName) {
    queue.on('error', (err) => {
      console.error(`[Queue:${queueName}] Error:`, err.message);
    });

    queue.on('waiting', (jobId) => {
      console.debug(`[Queue:${queueName}] Job ${jobId} esperando ser procesado`);
    });

    queue.on('active', (job) => {
      console.debug(`[Queue:${queueName}] Job ${job.id} empezó a procesarse`);
    });

    queue.on('completed', (job) => {
      console.debug(`[Queue:${queueName}] Job ${job.id} completado`);
    });

    queue.on('failed', (job, err) => {
      console.error(`[Queue:${queueName}] Job ${job?.id} falló:`, err.message);
    });

    queue.on('stalled', (jobId) => {
      console.warn(`[Queue:${queueName}] Job ${jobId} stalled (worker crash?)`);
    });

    queue.on('progress', (job, progress) => {
      console.debug(`[Queue:${queueName}] Job ${job.id} progreso: ${progress}%`);
    });
  }

  /**
   * Obtiene una cola existente por nombre
   * @param {string} queueName - Nombre de la cola
   * @returns {Queue|undefined} Instancia de cola o undefined si no existe
   */
  getQueue(queueName) {
    return this._queues.get(queueName);
  }

  /**
   * Cierra todas las colas y la conexión a Redis
   * @returns {Promise<void>}
   */
  async closeAll() {
    console.info('[QueueFactory] Cerrando todas las colas...');

    for (const [name, queue] of this._queues.entries()) {
      try {
        await queue.close();
        console.debug(`[QueueFactory] Cola ${name} cerrada`);
      } catch (err) {
        console.error(`[QueueFactory] Error cerrando cola ${name}:`, err.message);
      }
    }

    this._queues.clear();

    if (this._connection) {
      await this._connection.quit();
      this._connection = null;
      console.info('[QueueFactory] Conexión Redis cerrada');
    }
  }

  /**
   * Obtiene estadísticas de una cola
   * @param {string} queueName - Nombre de la cola
   * @returns {Promise<object>} Estadísticas de la cola
   */
  async getQueueStats(queueName) {
    const queue = this.getQueue(queueName);
    if (!queue) {
      throw new Error(`Cola ${queueName} no encontrada`);
    }

    const [waiting, active, completed, failed, delayed] = await Promise.all([
      queue.getWaitingCount(),
      queue.getActiveCount(),
      queue.getCompletedCount(),
      queue.getFailedCount(),
      queue.getDelayedCount(),
    ]);

    return {
      queueName,
      waiting,
      active,
      completed,
      failed,
      delayed,
      total: waiting + active + completed + failed + delayed,
    };
  }
}

// Exportar instancia singleton
module.exports = new QueueFactory();
