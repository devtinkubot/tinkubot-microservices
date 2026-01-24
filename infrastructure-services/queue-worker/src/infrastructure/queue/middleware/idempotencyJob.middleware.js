/**
 * idempotencyJob.middleware.js
 * Middleware de BullMQ para verificar idempotencia de jobs
 *
 * Responsabilidad:
 * - Prevenir procesamiento duplicado de jobs
 * - Verificar idempotencia usando Redis distribuido
 * - Marcar jobs como duplicados si ya fueron procesados
 *
 * Fase 1: Estabilización Crítica
 * Soluciona: WhatsApp reenviando webhooks
 */

const IdempotencyStore = require('../../cache/IdempotencyStore');

/**
 * Crea un middleware de idempotencia para BullMQ
 * @param {IdempotencyStore} idempotencyStore - Instancia de IdempotencyStore
 * @returns {function} Middleware function para BullMQ
 */
function createIdempotencyMiddleware(idempotencyStore) {
  if (!idempotencyStore) {
    throw new Error('[IdempotencyMiddleware] IdempotencyStore es requerido');
  }

  /**
   * Middleware function para BullMQ
   * @param {object} job - Job de BullMQ
   * @returns {Promise<void>}
   */
  return async function idempotencyMiddleware(job) {
    try {
      // Generar key de idempotencia para el job
      const jobKey = IdempotencyStore.generateJobKey(job.id);

      // Verificar si el job ya fue procesado
      const isFirstTime = await idempotencyStore.check(jobKey);

      if (!isFirstTime) {
        // Job ya fue procesado, marcar para skip
        console.warn(`[IdempotencyMiddleware] Job ${job.id} ya procesado (duplicado)`);

        // Actualizar datos del job para indicar que es duplicado
        job.data.isDuplicate = true;
        job.data.duplicateReason = 'idempotency_check_failed';

        // Notificar a BullMQ que debe saltar este job
        throw new Error(`Job ${job.id} es duplicado - saltando procesamiento`);
      }

      // Marcar el job como procesado exitosamente
      // El TTL se encargará de limpiar automáticamente después del tiempo configurado
      await idempotencyStore.markProcessed(jobKey);

      console.debug(`[IdempotencyMiddleware] Job ${job.id} marcado como procesado`);
    } catch (err) {
      // Si el error es por duplicado, relanzarlo para que BullMQ lo maneje
      if (err.message.includes('duplicado') || err.message.includes('saltando')) {
        throw err;
      }

      // Otro error, loggear pero no bloquear el procesamiento
      console.error(`[IdempotencyMiddleware] Error verificando idempotencia:`, err.message);

      // En caso de error en la verificación, es más seguro permitir el procesamiento
      // para no bloquear mensajes válidos por un fallo temporal
      console.warn(`[IdempotencyMiddleware] Permitiendo procesamiento de job ${job.id} a pesar del error`);
    }
  };
}

/**
 * Wrapper para aplicar el middleware a un worker de BullMQ
 * @param {Worker} worker - Instancia de Worker de BullMQ
 * @param {IdempotencyStore} idempotencyStore - Instancia de IdempotencyStore
 */
function applyIdempotencyMiddlewareToWorker(worker, idempotencyStore) {
  if (!worker) {
    throw new Error('[IdempotencyMiddleware] Worker es requerido');
  }

  const middleware = createIdempotencyMiddleware(idempotencyStore);

  // Aplicar middleware antes de procesar cada job
  worker.use(middleware);

  console.info('[IdempotencyMiddleware] Middleware aplicado al worker');
}

module.exports = {
  createIdempotencyMiddleware,
  applyIdempotencyMiddlewareToWorker,
};
