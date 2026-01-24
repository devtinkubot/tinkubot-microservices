/**
 * IdempotencyStore.js
 * Store de idempotencia distribuido usando Redis
 *
 * Responsabilidad:
 * - Prevenir procesamiento duplicado de mensajes
 * - Soportar múltiples instancias (distributed locking)
 * - Reemplazar sets en memoria por Redis cache
 *
 * Fase 1: Estabilización Crítica
 * Soluciona: WhatsApp reenviando webhooks + usuarios reenviando mensajes
 */

const DistributedCache = require('./DistributedCache');
const timeouts = require('../config/timeouts');

class IdempotencyStore {
  /**
   * @param {DistributedCache} distributedCache - Instancia de cache distribuido
   */
  constructor(distributedCache) {
    this._cache = distributedCache;
  }

  /**
   * Verifica si un key ya fue procesado y lo marca si no
   * @param {string} key - Key único (ej: messageId, phoneNumber)
   * @param {number} ttl - TTL en segundos (default: desde config)
   * @returns {Promise<boolean>} true si es primera vez (debe procesarse), false si ya existe
   */
  async check(key, ttl) {
    const effectiveTtl = ttl || timeouts.IDEMPOTENCY_TTL;
    const cacheKey = `idempotency:${key}`;

    try {
      // Verificar si ya existe
      const exists = await this._cache.exists(cacheKey);

      if (exists) {
        console.debug(`[IdempotencyStore] Key ${key} ya procesado (skip)`);
        return false; // Ya procesado, no procesar de nuevo
      }

      // Marcar como procesado
      await this._cache.set(cacheKey, { processed: true, timestamp: Date.now() }, effectiveTtl);
      console.debug(`[IdempotencyStore] Key ${key} marcado como procesado (TTL: ${effectiveTtl}s)`);
      return true; // Primera vez, procesar
    } catch (err) {
      console.error(`[IdempotencyStore] Error verificando key ${key}:`, err.message);
      // En caso de error, es más seguro permitir el procesamiento
      // para no bloquear mensajes válidos
      return true;
    }
  }

  /**
   * Marca explícitamente un key como procesado
   * @param {string} key - Key único
   * @param {number} ttl - TTL en segundos (default: desde config)
   * @returns {Promise<boolean>} true si se marcó correctamente
   */
  async markProcessed(key, ttl) {
    const effectiveTtl = ttl || timeouts.IDEMPOTENCY_TTL;
    const cacheKey = `idempotency:${key}`;

    try {
      await this._cache.set(cacheKey, { processed: true, timestamp: Date.now() }, effectiveTtl);
      console.debug(`[IdempotencyStore] Key ${key} marcado manualmente como procesado`);
      return true;
    } catch (err) {
      console.error(`[IdempotencyStore] Error marcando key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Verifica si un key está procesado sin marcarlo
   * @param {string} key - Key único
   * @returns {Promise<boolean>} true si ya fue procesado
   */
  async isProcessed(key) {
    const cacheKey = `idempotency:${key}`;

    try {
      return await this._cache.exists(cacheKey);
    } catch (err) {
      console.error(`[IdempotencyStore] Error verificando si key ${key} está procesado:`, err.message);
      return false;
    }
  }

  /**
   * Elimina un key del store (útil para testing o reintentos manuales)
   * @param {string} key - Key único
   * @returns {Promise<boolean>} true si se eliminó correctamente
   */
  async remove(key) {
    const cacheKey = `idempotency:${key}`;

    try {
      await this._cache.delete(cacheKey);
      console.debug(`[IdempotencyStore] Key ${key} eliminado del store`);
      return true;
    } catch (err) {
      console.error(`[IdempotencyStore] Error eliminando key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Genera un key de idempotencia para un mensaje de WhatsApp
   * @param {object} message - Mensaje de WhatsApp
   * @returns {string} Key único
   */
  static generateMessageKey(message) {
    const messageId = message.id?._serialized || message.id || 'unknown';
    return `whatsapp:message:${messageId}`;
  }

  /**
   * Genera un key de idempotencia para una sesión de usuario
   * @param {string} phoneNumber - Número de teléfono
   * @param {string} action - Acción específica (ej: "search", "state_transition")
   * @returns {string} Key único
   */
  static generateSessionKey(phoneNumber, action) {
    return `whatsapp:session:${phoneNumber}:${action}`;
  }

  /**
   * Genera un key de idempotencia para un job
   * @param {string} jobId - ID del job
   * @returns {string} Key único
   */
  static generateJobKey(jobId) {
    return `whatsapp:job:${jobId}`;
  }
}

module.exports = IdempotencyStore;
