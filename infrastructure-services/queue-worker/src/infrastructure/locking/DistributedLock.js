/**
 * DistributedLock.js
 * Implementación de Distributed Lock usando Redlock
 *
 * Responsabilidad:
 * - Proporcionar locking distribuido entre múltiples instancias
 * - Prevenir race conditions en operaciones críticas
 * - Prevenir corrupción de state machine
 *
 * Fase 1: Estabilización Crítica
 * Soluciona: Múltiples mensajes simultáneos del mismo usuario
 */

const Redlock = require('redlock');
const Redis = require('ioredis');
const timeouts = require('../config/timeouts');

class DistributedLock {
  /**
   * @param {string} redisUrl - URL de conexión a Redis
   * @param {string} redisPassword - Password de Redis (opcional)
   */
  constructor(redisUrl, redisPassword) {
    this._redisUrl = redisUrl || process.env.REDIS_URL || 'redis://localhost:6379';
    this._redisPassword = redisPassword || process.env.REDIS_PASSWORD;
    this._redlock = null;
  }

  /**
   * Inicializa la conexión a Redis y Redlock
   * @returns {DistributedLock} this (fluent interface)
   */
  async initialize() {
    if (this._redlock) {
      console.warn('[DistributedLock] Ya inicializado');
      return this;
    }

    console.info('[DistributedLock] Inicializando...');

    // Crear cliente Redis para Redlock
    const redisClient = new Redis(this._redisUrl, {
      password: this._redisPassword,
      maxRetriesPerRequest: 3,
    });

    // Configurar event handlers
    redisClient.on('error', (err) => {
      console.error('[DistributedLock] Redis client error:', err.message);
    });

    // Crear instancia de Redlock
    this._redlock = new Redlock([redisClient], {
      // Duración que consideraremos "drift" antes de renovar
      driftFactor: 0.01, // Tiempo de drift multiplicado por el TTL
      // Número mínimo de reintentos antes de rendirse
      retryCount: 10,
      // Tiempo mínimo entre reintentos
      retryMinDelay: 200, // ms
      // Tiempo máximo entre reintentos
      retryMaxDelay: 1000, // ms
    });

    // Event handlers de Redlock
    this._redlock.on('clientError', (err) => {
      console.error('[DistributedLock] Redlock client error:', err.message);
    });

    console.info('[DistributedLock] Inicializado');
    return this;
  }

  /**
   * Adquiere un lock distribuido
   * @param {string} lockKey - Key único para el lock
   * @param {number} ttl - TTL del lock en milisegundos (default: desde config)
   * @returns {Promise<Lock|null>} Lock object o null si no se pudo adquirir
   */
  async acquireLock(lockKey, ttl) {
    if (!this._redlock) {
      throw new Error('[DistributedLock] No inicializado. Llamar a initialize() primero.');
    }

    const effectiveTtl = ttl || timeouts.SESSION_LOCK_TTL;
    const resourceKey = `lock:${lockKey}`;

    try {
      const lock = await this._redlock.acquire([resourceKey], effectiveTtl);
      console.debug(`[DistributedLock] Lock adquirido: ${lockKey} (TTL: ${effectiveTtl}ms)`);
      return lock;
    } catch (err) {
      if (err.name === 'LockError') {
        console.debug(`[DistributedLock] No se pudo adquirir lock: ${lockKey} (ya está tomado)`);
        return null;
      }

      console.error(`[DistributedLock] Error adquiriendo lock ${lockKey}:`, err.message);
      return null;
    }
  }

  /**
   * Libera un lock previamente adquirido
   * @param {Lock} lock - Lock object a liberar
   * @returns {Promise<boolean>} true si se liberó correctamente
   */
  async releaseLock(lock) {
    if (!lock) {
      console.warn('[DistributedLock] Intentando liberar lock nulo');
      return false;
    }

    try {
      // En Redlock v4, se usa redlock.release(lock) no lock.release()
      await this._redlock.release(lock);
      console.debug('[DistributedLock] Lock liberado');
      return true;
    } catch (err) {
      console.error('[DistributedLock] Error liberando lock:', err.message);
      return false;
    }
  }

  /**
   * Ejecuta una función con un lock activo (pattern: lock-and-run)
   * @param {string} lockKey - Key único para el lock
   * @param {function} fn - Función a ejecutar con el lock activo
   * @param {number} ttl - TTL del lock en milisegundos (default: desde config)
   * @returns {Promise<any>} Resultado de la función
   */
  async runWithLock(lockKey, fn, ttl) {
    let lock;

    try {
      // Adquirir lock
      lock = await this.acquireLock(lockKey, ttl);

      if (!lock) {
        throw new Error(`No se pudo adquirir lock para: ${lockKey}`);
      }

      // Ejecutar función con lock activo
      console.debug(`[DistributedLock] Ejecutando función con lock: ${lockKey}`);
      const result = await fn();

      return result;
    } finally {
      // Siempre liberar el lock, incluso si la función falló
      if (lock) {
        await this.releaseLock(lock);
      }
    }
  }

  /**
   * Verifica si un lock está activo
   * @param {string} lockKey - Key del lock a verificar
   * @returns {Promise<boolean>} true si el lock está activo
   */
  async isLocked(lockKey) {
    if (!this._redlock) {
      throw new Error('[DistributedLock] No inicializado');
    }

    const resourceKey = `lock:${lockKey}`;

    try {
      // Intentar adquirir el lock con TTL muy corto
      // Si se puede adquirir, significa que nadie lo tenía
      const lock = await this._redlock.acquire([resourceKey], 10);

      // Si llegamos aquí, el lock estaba libre
      await this._redlock.release(lock);
      return false;
    } catch (err) {
      if (err.name === 'LockError') {
        // No se pudo adquirir = lock está tomado
        return true;
      }
      throw err;
    }
  }

  /**
   * Cierra la conexión a Redis
   * @returns {Promise<void>}
   */
  async close() {
    // Redlock no tiene método close, pero podemos limpiar la instancia
    this._redlock = null;
    console.info('[DistributedLock] Conexión cerrada');
  }
}

/**
 * Clase Lock que representa un lock activo
 * Nota: Redlock ya provee su propia clase Lock, esta es solo para referencia
 */
class Lock {
  constructor(resource, value, expiration) {
    this.resource = resource;
    this.value = value;
    this.expiration = expiration;
  }

  async release() {
    // Implementación de release está en Redlock
    // Esta clase es solo para documentación
  }
}

module.exports = DistributedLock;
