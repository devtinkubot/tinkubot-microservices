/**
 * DistributedCache.js
 * Cache distribuido usando Redis con soporte TTL
 *
 * Responsabilidad:
 * - Proporcionar una capa de cache distribuido
 * - Manejar TTL automático para evitar memory leaks
 * - Soportar operaciones get/set/delete básicas
 *
 * Fase 1: Estabilización Crítica
 * Reemplaza sets en memoria por Redis para soportar scaling horizontal
 */

const Redis = require('ioredis');

class DistributedCache {
  /**
   * @param {string} redisUrl - URL de conexión a Redis
   * @param {string} redisPassword - Password de Redis (opcional)
   */
  constructor(redisUrl, redisPassword) {
    this._redisUrl = redisUrl || process.env.REDIS_URL || 'redis://localhost:6379';
    this._redisPassword = redisPassword || process.env.REDIS_PASSWORD;
    this._client = null;
  }

  /**
   * Inicializa la conexión a Redis
   * @returns {DistributedCache} this (fluent interface)
   */
  async initialize() {
    if (this._client) {
      console.warn('[DistributedCache] Ya inicializado');
      return this;
    }

    console.info('[DistributedCache] Inicializando conexión Redis...');

    this._client = new Redis(this._redisUrl, {
      password: this._redisPassword,
      maxRetriesPerRequest: 3,
      enableReadyCheck: true,
      retryStrategy: (times) => {
        const delay = Math.min(times * 50, 500);
        return delay;
      },
    });

    // Event handlers
    this._client.on('error', (err) => {
      console.error('[DistributedCache] Redis error:', err.message);
    });

    this._client.on('connect', () => {
      console.info('[DistributedCache] Redis conectado');
    });

    // Esperar a que Redis esté listo
    await this._client.ping();

    return this;
  }

  /**
   * Obtiene un valor del cache
   * @param {string} key - Clave a buscar
   * @returns {Promise<string|null>} Valor o null si no existe
   */
  async get(key) {
    if (!this._client) {
      throw new Error('[DistributedCache] No inicializado. Llamar a initialize() primero.');
    }

    try {
      const value = await this._client.get(`cache:${key}`);
      return value;
    } catch (err) {
      console.error(`[DistributedCache] Error obteniendo key ${key}:`, err.message);
      return null;
    }
  }

  /**
   * Obtiene y parsea un valor JSON del cache
   * @param {string} key - Clave a buscar
   * @returns {Promise<object|null>} Objeto parseado o null si no existe
   */
  async getJSON(key) {
    const value = await this.get(key);
    if (!value) return null;

    try {
      return JSON.parse(value);
    } catch (err) {
      console.error(`[DistributedCache] Error parseando JSON de key ${key}:`, err.message);
      return null;
    }
  }

  /**
   * Guarda un valor en el cache con TTL
   * @param {string} key - Clave a guardar
   * @param {any} value - Valor a guardar (se convertirá a string)
   * @param {number} ttl - TTL en segundos (default: 300 = 5 minutos)
   * @returns {Promise<boolean>} true si se guardó correctamente
   */
  async set(key, value, ttl = 300) {
    if (!this._client) {
      throw new Error('[DistributedCache] No inicializado. Llamar a initialize() primero.');
    }

    try {
      const stringValue = typeof value === 'string' ? value : JSON.stringify(value);
      await this._client.setex(`cache:${key}`, ttl, stringValue);
      return true;
    } catch (err) {
      console.error(`[DistributedCache] Error guardando key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Guarda un objeto JSON en el cache con TTL
   * @param {string} key - Clave a guardar
   * @param {object} value - Objeto a guardar
   * @param {number} ttl - TTL en segundos (default: 300)
   * @returns {Promise<boolean>} true si se guardó correctamente
   */
  async setJSON(key, value, ttl = 300) {
    return this.set(key, value, ttl);
  }

  /**
   * Elimina una clave del cache
   * @param {string} key - Clave a eliminar
   * @returns {Promise<boolean>} true si se eliminó correctamente
   */
  async delete(key) {
    if (!this._client) {
      throw new Error('[DistributedCache] No inicializado. Llamar a initialize() primero.');
    }

    try {
      await this._client.del(`cache:${key}`);
      return true;
    } catch (err) {
      console.error(`[DistributedCache] Error eliminando key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Verifica si una clave existe en el cache
   * @param {string} key - Clave a verificar
   * @returns {Promise<boolean>} true si existe
   */
  async exists(key) {
    if (!this._client) {
      throw new Error('[DistributedCache] No inicializado. Llamar a initialize() primero.');
    }

    try {
      const result = await this._client.exists(`cache:${key}`);
      return result === 1;
    } catch (err) {
      console.error(`[DistributedCache] Error verificando key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Establece un TTL para una clave existente
   * @param {string} key - Clave a modificar
   * @param {number} ttl - Nuevo TTL en segundos
   * @returns {Promise<boolean>} true si se modificó correctamente
   */
  async expire(key, ttl) {
    if (!this._client) {
      throw new Error('[DistributedCache] No inicializado. Llamar a initialize() primero.');
    }

    try {
      await this._client.expire(`cache:${key}`, ttl);
      return true;
    } catch (err) {
      console.error(`[DistributedCache] Error estableciendo TTL para key ${key}:`, err.message);
      return false;
    }
  }

  /**
   * Cierra la conexión a Redis
   * @returns {Promise<void>}
   */
  async close() {
    if (this._client) {
      await this._client.quit();
      this._client = null;
      console.info('[DistributedCache] Conexión cerrada');
    }
  }

  /**
   * Obtiene el cliente Redis subyacente
   * @returns {Redis} Cliente Redis
   */
  getClient() {
    return this._client;
  }
}

module.exports = DistributedCache;
