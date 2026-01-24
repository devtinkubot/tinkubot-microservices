/**
 * CircuitBreaker.js
 * Wrapper genérico de Circuit Breaker usando Opossum
 *
 * Responsabilidad:
 * - Proporcionar una capa de aislamiento de fallos
 * - Prevenir cascading failures
 * - Habilitar fallback cuando el servicio falla
 *
 * Fase 1: Estabilización Crítica
 * Protege contra: AI service caído = todo el sistema cae
 */

const CircuitBreaker = require('opossum');
const timeouts = require('../config/timeouts');

class GenericCircuitBreaker {
  /**
   * @param {function} action - Función a proteger con circuit breaker
   * @param {object} options - Opciones de configuración
   */
  constructor(action, options = {}) {
    const defaultOptions = {
      timeout: timeouts.CIRCUIT_BREAKER_TIMEOUT,
      errorThresholdPercentage: 50, // Abrir circuito si 50% de requests fallan
      resetTimeout: timeouts.CIRCUIT_RESET_TIMEOUT, // Tiempo antes de intentar cerrar circuito
      rollingCountTimeout: 10000, // Ventana de tiempo para calcular estadísticas
      rollingCountBuckets: 10, // Número de buckets en la ventana
      name: options.name || 'GenericCircuitBreaker',
    };

    this._options = { ...defaultOptions, ...options };
    this._action = action;
    this._fallback = options.fallback;
    this._breaker = null;
    this._status = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
  }

  /**
   * Inicializa el circuit breaker
   * @returns {GenericCircuitBreaker} this (fluent interface)
   */
  initialize() {
    if (this._breaker) {
      console.warn(`[CircuitBreaker:${this._options.name}] Ya inicializado`);
      return this;
    }

    console.info(`[CircuitBreaker:${this._options.name}] Inicializando...`);

    // Crear circuit breaker con Opossum
    this._breaker = new CircuitBreaker(this._action, this._options);

    // Configurar fallback si existe
    if (this._fallback) {
      this._breaker.fallback(this._fallback);
    }

    // Configurar event handlers
    this._setupEventHandlers();

    console.info(`[CircuitBreaker:${this._options.name}] Inicializado (status: ${this._status})`);
    return this;
  }

  /**
   * Configura event handlers para el circuit breaker
   * @private
   */
  _setupEventHandlers() {
    const name = this._options.name;

    this._breaker.on('open', () => {
      this._status = 'OPEN';
      console.error(`[CircuitBreaker:${name}] CIRCUITO ABIERTO - Usando fallback`);
    });

    this._breaker.on('halfOpen', () => {
      this._status = 'HALF_OPEN';
      console.warn(`[CircuitBreaker:${name}] CIRCUITO MEDIO ABIERTO - Probando servicio`);
    });

    this._breaker.on('close', () => {
      this._status = 'CLOSED';
      console.info(`[CircuitBreaker:${name}] CIRCUITO CERRADO - Servicio normal`);
    });

    this._breaker.on('fallback', (result) => {
      console.debug(`[CircuitBreaker:${name}] Fallback ejecutado`);
    });

    this._breaker.on('reject', () => {
      console.warn(`[CircuitBreaker:${name}] Request rechazado (circuito abierto)`);
    });

    this._breaker.on('timeout', () => {
      console.warn(`[CircuitBreaker:${name}] Timeout ejecutando acción`);
    });

    this._breaker.on('success', (result) => {
      console.debug(`[CircuitBreaker:${name}] Request exitoso`);
    });

    this._breaker.on('failure', (err) => {
      console.error(`[CircuitBreaker:${name}] Request falló:`, err.message);
    });

    // Snapshot de estadísticas periódicamente
    this._breaker.on('snapshot', (snapshot) => {
      console.debug(`[CircuitBreaker:${name}] Snapshot:`, {
        failures: snapshot.failures,
        successes: snapshot.successes,
        rejects: snapshot.rejects,
        fires: snapshot.fires,
      });
    });
  }

  /**
   * Ejecuta la acción protegida por el circuit breaker
   * @param {...any} args - Argumentos para pasar a la acción
   * @returns {Promise<any>} Resultado de la acción o del fallback
   */
  async execute(...args) {
    if (!this._breaker) {
      throw new Error(`[CircuitBreaker:${this._options.name}] No inicializado. Llamar a initialize() primero.`);
    }

    try {
      return await this._breaker.fire(...args);
    } catch (err) {
      console.error(`[CircuitBreaker:${this._options.name}] Error en execute:`, err.message);
      throw err;
    }
  }

  /**
   * Obtiene el estado actual del circuit breaker
   * @returns {string} Estado: 'CLOSED', 'OPEN', o 'HALF_OPEN'
   */
  getStatus() {
    return this._status;
  }

  /**
   * Obtiene estadísticas del circuit breaker
   * @returns {object} Estadísticas
   */
  getStats() {
    if (!this._breaker) {
      throw new Error(`[CircuitBreaker:${this._options.name}] No inicializado`);
    }

    const stats = this._breaker.stats;
    return {
      name: this._options.name,
      status: this._status,
      failures: stats.failures,
      successes: stats.successes,
      rejects: stats.rejects,
      fires: stats.fires,
      fallbacks: stats.fallbacks,
      errorPercentage: this._calculateErrorPercentage(stats),
    };
  }

  /**
   * Calcula el porcentaje de error
   * @private
   * @param {object} stats - Estadísticas del breaker
   * @returns {number} Porcentaje de error
   */
  _calculateErrorPercentage(stats) {
    const total = stats.failures + stats.successes + stats.rejects;
    if (total === 0) return 0;
    return Math.round((stats.failures / total) * 100);
  }

  /**
   * Abre manualmente el circuito (útil para maintenance mode)
   * @returns {void}
   */
  open() {
    if (this._breaker) {
      this._breaker.open();
      console.warn(`[CircuitBreaker:${this._options.name}] Circuito abierto manualmente`);
    }
  }

  /**
   * Cierra manualmente el circuito
   * @returns {void}
   */
  close() {
    if (this._breaker) {
      this._breaker.close();
      console.info(`[CircuitBreaker:${this._options.name}] Circuito cerrado manualmente`);
    }
  }

  /**
   * Habilita el half-open state manualmente
   * @returns {void}
   */
  halfOpen() {
    if (this._breaker) {
      this._breaker.halfOpen();
      console.warn(`[CircuitBreaker:${this._options.name}] Circuito en half-open manualmente`);
    }
  }
}

module.exports = GenericCircuitBreaker;
