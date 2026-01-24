/**
 * workerLogger.js
 * Logging especializado para Queue Workers
 *
 * Responsabilidad:
 * - Proporcionar logging estructurado para workers
 * - Agregar metadata específica de jobs
 * - Facilitar debugging y monitoreo
 *
 * Fase 1: Estabilización Crítica
 */

const instanceId = process.env.CLIENTES_INSTANCE_ID || 'worker-clientes';
const instanceName = process.env.CLIENTES_INSTANCE_NAME || 'TinkuBot Worker Clientes';

class WorkerLogger {
  constructor() {
    this._logLevel = process.env.LOG_LEVEL || 'info';
  }

  /**
   * Log nivel debug
   * @param {string} message - Mensaje a loggear
   * @param {object} meta - Metadata adicional
   */
  debug(message, meta = {}) {
    if (this._shouldLog('debug')) {
      console.debug(JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'debug',
        instance: instanceName,
        instanceId,
        ...meta,
        message,
      }));
    }
  }

  /**
   * Log nivel info
   * @param {string} message - Mensaje a loggear
   * @param {object} meta - Metadata adicional
   */
  info(message, meta = {}) {
    if (this._shouldLog('info')) {
      console.info(JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'info',
        instance: instanceName,
        instanceId,
        ...meta,
        message,
      }));
    }
  }

  /**
   * Log nivel warn
   * @param {string} message - Mensaje a loggear
   * @param {object} meta - Metadata adicional
   */
  warn(message, meta = {}) {
    if (this._shouldLog('warn')) {
      console.warn(JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'warn',
        instance: instanceName,
        instanceId,
        ...meta,
        message,
      }));
    }
  }

  /**
   * Log nivel error
   * @param {string} message - Mensaje a loggear
   * @param {object} meta - Metadata adicional
   */
  error(message, meta = {}) {
    if (this._shouldLog('error')) {
      console.error(JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'error',
        instance: instanceName,
        instanceId,
        ...meta,
        message,
      }));
    }
  }

  /**
   * Log específico para inicio de job
   * @param {object} job - Job de BullMQ
   */
  logJobStart(job) {
    this.info('Job started', {
      jobId: job.id,
      jobName: job.name,
      attempts: job.attemptsMade,
      data: {
        from: job.data.message?.from,
        messageId: job.data.message?.id,
      },
    });
  }

  /**
   * Log específico para job completado
   * @param {object} job - Job de BullMQ
   * @param {number} duration - Duración en ms
   */
  logJobComplete(job, duration) {
    this.info('Job completed', {
      jobId: job.id,
      jobName: job.name,
      attempts: job.attemptsMade,
      duration: `${duration}ms`,
    });
  }

  /**
   * Log específico para job fallido
   * @param {object} job - Job de BullMQ
   * @param {Error} error - Error que causó el fallo
   * @param {number} duration - Duración en ms
   */
  logJobFailed(job, error, duration) {
    this.error('Job failed', {
      jobId: job?.id,
      jobName: job?.name,
      attempts: job?.attemptsMade,
      duration: `${duration}ms`,
      error: {
        message: error?.message,
        stack: error?.stack,
      },
    });
  }

  /**
   * Log específico para job con error de idempotencia
   * @param {object} job - Job de BullMQ
   */
  logJobDuplicate(job) {
    this.warn('Job es duplicado, saltando', {
      jobId: job.id,
      jobName: job.name,
      reason: job.data.duplicateReason,
    });
  }

  /**
   * Log específico para lock acquisition
   * @param {string} phoneNumber - Número de teléfono
   * @param {boolean} acquired - Si se adquirió el lock
   */
  logLockAttempt(phoneNumber, acquired) {
    if (acquired) {
      this.debug('Lock adquirido', { phoneNumber });
    } else {
      this.warn('Lock no disponible', { phoneNumber });
    }
  }

  /**
   * Log específico para feedback enviado
   * @param {string} phoneNumber - Número de teléfono
   * @param {string} feedbackType - Tipo de feedback
   */
  logFeedbackSent(phoneNumber, feedbackType) {
    this.debug('Feedback enviado', { phoneNumber, feedbackType });
  }

  /**
   * Verifica si debe loggear según el nivel configurado
   * @private
   * @param {string} level - Nivel a verificar
   * @returns {boolean} true si debe loggear
   */
  _shouldLog(level) {
    const levels = ['debug', 'info', 'warn', 'error'];
    const currentLevelIndex = levels.indexOf(this._logLevel);
    const requestedLevelIndex = levels.indexOf(level);

    return requestedLevelIndex >= currentLevelIndex;
  }
}

// Exportar instancia singleton
module.exports = new WorkerLogger();
