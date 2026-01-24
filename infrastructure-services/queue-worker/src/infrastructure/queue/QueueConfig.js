/**
 * QueueConfig.js
 * Configuración de colas BullMQ y conexión a Redis
 *
 * Responsabilidad:
 * - Crear y configurar la conexión a Redis
 * - Proveer configuración para colas y workers
 * - Centralizar opciones de BullMQ
 *
 * Fase 1: Estabilización Crítica
 */

const { Queue, Worker, QueueScheduler } = require('bullmq');
const Redis = require('ioredis');

class QueueConfig {
  /**
   * Crea una conexión a Redis optimizada para BullMQ
   * @returns {Redis} Instancia de Redis configurada
   */
  static createRedisConnection() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    const redisPassword = process.env.REDIS_PASSWORD;

    console.info(`[BullMQ] Conectando a Redis: ${redisUrl.replace(/:[^:@]+@/, ':****@')}`);

    const connection = new Redis(redisUrl, {
      password: redisPassword,
      maxRetriesPerRequest: null, // BullMQ v5 requiere null
      enableReadyCheck: false,
      enableOfflineQueue: false, // Importante para workers
      retryStrategy: (times) => {
        const delay = Math.min(times * 50, 500);
        return delay;
      },
      // Opciones de reconnexión
      reconnectOnError: (err) => {
        const targetError = 'READONLY';
        if (err.message.includes(targetError)) {
          // Solo reconectar cuando el error indica que la conexión fue cerrada
          console.error('[BullMQ] Redis error de reconexión:', err.message);
          return true;
        }
        return false;
      },
    });

    // Manejo de errores de conexión
    connection.on('error', (err) => {
      console.error('[BullMQ] Redis connection error:', err.message);
    });

    connection.on('connect', () => {
      console.info('[BullMQ] Redis conectado exitosamente');
    });

    connection.on('close', () => {
      console.warn('[BullMQ] Redis connection cerrada');
    });

    return connection;
  }

  /**
   * Opciones por defecto para colas BullMQ
   */
  static get defaultQueueOptions() {
    const prefix = process.env.BULLMQ_PREFIX || 'tinkubot';

    return {
      connection: QueueConfig.createRedisConnection(),
      prefix: `${prefix}:bullmq`,
      defaultJobOptions: {
        attempts: parseInt(process.env.QUEUE_MAX_RETRIES || '3', 10),
        backoff: {
          type: 'exponential',
          delay: 2000,
        },
        removeOnComplete: {
          count: 1000, // Mantener últimos 1000 jobs completados
          age: 24 * 3600, // O 24 horas
        },
        removeOnFail: {
          count: 5000, // Mantener últimos 5000 jobs fallidos para debugging
          age: 7 * 24 * 3600, // O 7 días
        },
      },
    };
  }

  /**
   * Opciones por defecto para workers BullMQ
   */
  static get defaultWorkerOptions() {
    const prefix = process.env.BULLMQ_PREFIX || 'tinkubot';
    const concurrency = parseInt(process.env.QUEUE_CONCURRENCY || '10', 10);

    return {
      connection: QueueConfig.createRedisConnection(),
      prefix: `${prefix}:bullmq`,
      concurrency,
      limiter: {
        max: 100, // Máximo 100 jobs por ventana
        duration: 1000, // Ventana de 1 segundo
      },
    };
  }

  /**
   * Obtiene el nombre de la cola de webhooks entrantes
   * Nota: BullMQ no permite ':' en los nombres de cola, se usan guiones
   */
  static get WEBHOOK_QUEUE_NAME() {
    return 'whatsapp-webhooks-incoming';
  }

  /**
   * Obtiene el nombre de la cola de dead letter
   * Nota: BullMQ no permite ':' en los nombres de cola, se usan guiones
   */
  static get DLQ_QUEUE_NAME() {
    return 'whatsapp-webhooks-dlq';
  }
}

module.exports = QueueConfig;
