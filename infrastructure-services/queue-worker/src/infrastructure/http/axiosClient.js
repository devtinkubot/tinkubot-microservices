/**
 * axiosClient.js
 * Cliente HTTP con configuración de reintentos y timeouts
 *
 * Responsabilidad:
 * - Configurar cliente axios con keep-alive
 * - Implementar lógica de reintentos con backoff exponencial
 * - Manejar errores HTTP recuperables
 *
 * Fase 1: Estabilización Crítica
 * Cambios:
 * - Agregado jitter a exponential backoff (previene thundering herd)
 * - Timeouts actualizados desde configuración centralizada
 */

const axios = require('axios');
const http = require('http');
const https = require('https');
const config = require('../config/envConfig');
const timeouts = require('../config/timeouts');

/**
 * Clase AxiosClient con capacidades de reintentos
 */
class AxiosClient {
  constructor() {
    // Configurar HTTP agents para keep-alive
    const httpAgent = new http.Agent(config.httpAgent);
    const httpsAgent = new https.Agent(config.httpAgent);

    // Crear cliente axios con configuración optimizada
    this.client = axios.create({
      httpAgent,
      httpsAgent,
      timeout: timeouts.AI_SERVICE_TIMEOUT, // FASE 1: Timeout desde config centralizada
    });
  }

  /**
   * Calcula delay con jitter para evitar thundering herd
   * @private
   * @param {number} attempt - Número de intento actual
   * @param {number} baseDelay - Delay base en ms
   * @returns {number} Delay con jitter aplicado
   */
  _calculateDelayWithJitter(attempt, baseDelay) {
    // Exponential backoff: 300ms, 600ms, 1200ms, 2400ms...
    const exponentialDelay = baseDelay * Math.pow(timeouts.RETRY_MULTIPLIER, attempt);

    // FASE 1: Agregar jitter aleatorio (±30% del delay)
    // Esto distribuye los retries en el tiempo para evitar thundering herd
    const jitter = Math.random() * 0.3 * exponentialDelay;
    const delayWithJitter = exponentialDelay + jitter;

    return Math.floor(delayWithJitter);
  }

  /**
   * Realiza una petición POST con reintentos automáticos
   * @param {string} url - URL de destino
   * @param {object} payload - Cuerpo de la petición
   * @param {object} options - Opciones adicionales
   * @param {number} options.timeout - Timeout en ms (default: desde config)
   * @param {number} options.retries - Número de reintentos (default: 2)
   * @param {number} options.baseDelay - Delay base en ms (default: desde config)
   * @returns {Promise<Response>} Respuesta HTTP
   */
  async postWithRetry(url, payload, { timeout, retries, baseDelay } = {}) {
    // FASE 1: Usar timeouts desde configuración centralizada
    const effectiveTimeout = timeout || timeouts.AI_SERVICE_TIMEOUT;
    const effectiveRetries = retries !== undefined ? retries : timeouts.RETRY_MAX_ATTEMPTS;
    const effectiveBaseDelay = baseDelay || timeouts.RETRY_BASE_DELAY;

    let attempt = 0;
    let lastErr;

    while (attempt <= effectiveRetries) {
      try {
        return await this.client.post(url, payload, { timeout: effectiveTimeout });
      } catch (err) {
        lastErr = err;
        const msg = err?.message || '';

        // Determinar si el error es recuperable
        const retriable = /ENOTFOUND|ECONNRESET|ETIMEDOUT|EAI_AGAIN|timeout/i.test(msg);

        if (!retriable || attempt === effectiveRetries) {
          throw err;
        }

        // FASE 1: Calcular delay con jitter para evitar thundering herd
        const delay = this._calculateDelayWithJitter(attempt, effectiveBaseDelay);
        console.warn(`[AxiosClient] HTTP retry ${attempt + 1}/${effectiveRetries} en ${delay}ms: ${msg}`);
        await new Promise(r => setTimeout(r, delay));
        attempt++;
      }
    }

    throw lastErr;
  }

  /**
   * Obtiene el cliente axios subyacente
   * @returns {AxiosInstance} Cliente axios
   */
  getClient() {
    return this.client;
  }

  /**
   * Realiza una petición GET simple
   * @param {string} url - URL de destino
   * @param {object} options - Opciones de axios
   * @returns {Promise<Response>} Respuesta HTTP
   */
  async get(url, options = {}) {
    return this.client.get(url, options);
  }

  /**
   * Realiza una petición POST simple
   * @param {string} url - URL de destino
   * @param {object} data - Cuerpo de la petición
   * @param {object} options - Opciones de axios
   * @returns {Promise<Response>} Respuesta HTTP
   */
  async post(url, data, options = {}) {
    return this.client.post(url, data, options);
  }
}

// Exportar instancia singleton
module.exports = new AxiosClient();
