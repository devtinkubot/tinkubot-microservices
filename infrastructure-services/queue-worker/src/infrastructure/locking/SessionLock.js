/**
 * SessionLock.js
 * Lock distribuido específico para sesiones de usuario
 *
 * Responsabilidad:
 * - Prevenir procesamiento simultáneo de mensajes del mismo usuario
 * - Evitar corrupción de state machine
 * - Serializar operaciones críticas por phoneNumber
 *
 * Fase 1: Estabilización Crítica
 * Soluciona: Usuario impaciente enviando múltiples mensajes
 */

const DistributedLock = require('./DistributedLock');
const timeouts = require('../config/timeouts');

class SessionLock {
  /**
   * @param {DistributedLock} distributedLock - Instancia de DistributedLock
   */
  constructor(distributedLock) {
    this._distributedLock = distributedLock;
  }

  /**
   * Adquiere un lock para una sesión de usuario
   * @param {string} phoneNumber - Número de teléfono del usuario
   * @param {number} ttl - TTL del lock en milisegundos (default: desde config)
   * @returns {Promise<Lock|null>} Lock object o null si no se pudo adquirir
   */
  async acquireLock(phoneNumber, ttl) {
    if (!phoneNumber) {
      throw new Error('[SessionLock] phoneNumber es requerido');
    }

    const lockKey = this._generateLockKey(phoneNumber);
    const effectiveTtl = ttl || timeouts.SESSION_LOCK_TTL;

    console.debug(`[SessionLock] Intentando adquirir lock para ${phoneNumber}`);

    return await this._distributedLock.acquireLock(lockKey, effectiveTtl);
  }

  /**
   * Libera un lock de sesión
   * @param {Lock} lock - Lock object a liberar
   * @returns {Promise<boolean>} true si se liberó correctamente
   */
  async releaseLock(lock) {
    return await this._distributedLock.releaseLock(lock);
  }

  /**
   * Ejecuta una función con un lock de sesión activo
   * @param {string} phoneNumber - Número de teléfono
   * @param {function} fn - Función a ejecutar
   * @param {number} ttl - TTL del lock (default: desde config)
   * @returns {Promise<any>} Resultado de la función
   */
  async runWithLock(phoneNumber, fn, ttl) {
    const lockKey = this._generateLockKey(phoneNumber);
    const effectiveTtl = ttl || timeouts.SESSION_LOCK_TTL;

    return await this._distributedLock.runWithLock(lockKey, fn, effectiveTtl);
  }

  /**
   * Verifica si una sesión está lockeada
   * @param {string} phoneNumber - Número de teléfono
   * @returns {Promise<boolean>} true si la sesión está lockeada
   */
  async isLocked(phoneNumber) {
    const lockKey = this._generateLockKey(phoneNumber);
    return await this._distributedLock.isLocked(lockKey);
  }

  /**
   * Genera un key de lock para un phoneNumber
   * @private
   * @param {string} phoneNumber - Número de teléfono
   * @returns {string} Key de lock
   */
  _generateLockKey(phoneNumber) {
    // Normalizar phoneNumber (remover +, espacios, guiones)
    const normalized = phoneNumber.replace(/[\s+-]/g, '');
    return `session:whatsapp:${normalized}`;
  }

  /**
   * Genera un key de lock para una acción específica dentro de una sesión
   * @param {string} phoneNumber - Número de teléfono
   * @param {string} action - Acción específica (ej: "state_transition", "search")
   * @returns {string} Key de lock
   */
  generateActionLockKey(phoneNumber, action) {
    const normalized = phoneNumber.replace(/[\s+-]/g, '');
    return `session:whatsapp:${normalized}:${action}`;
  }

  /**
   * Adquiere un lock para una acción específica de una sesión
   * @param {string} phoneNumber - Número de teléfono
   * @param {string} action - Acción específica
   * @param {number} ttl - TTL del lock (default: desde config)
   * @returns {Promise<Lock|null>} Lock object o null
   */
  async acquireActionLock(phoneNumber, action, ttl) {
    const lockKey = this.generateActionLockKey(phoneNumber, action);
    const effectiveTtl = ttl || timeouts.SESSION_LOCK_TTL;

    return await this._distributedLock.acquireLock(lockKey, effectiveTtl);
  }

  /**
   * Ejecuta una función con un lock de acción activo
   * @param {string} phoneNumber - Número de teléfono
   * @param {string} action - Acción específica
   * @param {function} fn - Función a ejecutar
   * @param {number} ttl - TTL del lock (default: desde config)
   * @returns {Promise<any>} Resultado de la función
   */
  async runWithActionLock(phoneNumber, action, fn, ttl) {
    const lockKey = this.generateActionLockKey(phoneNumber, action);
    const effectiveTtl = ttl || timeouts.SESSION_LOCK_TTL;

    return await this._distributedLock.runWithLock(lockKey, fn, effectiveTtl);
  }
}

module.exports = SessionLock;
