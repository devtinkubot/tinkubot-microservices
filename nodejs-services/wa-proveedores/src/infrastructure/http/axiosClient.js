/**
 * axiosClient.js
 * Cliente HTTP con configuración de reintentos y timeouts
 *
 * Responsabilidad:
 * - Configurar cliente axios con keep-alive
 * - Implementar lógica de reintentos con backoff exponencial
 * - Manejar errores HTTP recuperables
 */

const axios = require('axios');
const http = require('http');
const https = require('https');
const config = require('../config/envConfig');

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
      timeout: config.axiosTimeout
    });
  }

  /**
   * Realiza una petición POST con reintentos automáticos
   * @param {string} url - URL de destino
   * @param {object} payload - Cuerpo de la petición
   * @param {object} options - Opciones adicionales
   * @param {number} options.timeout - Timeout en ms (default: 15000)
   * @param {number} options.retries - Número de reintentos (default: 2)
   * @param {number} options.baseDelay - Delay base en ms (default: 300)
   * @returns {Promise<Response>} Respuesta HTTP
   */
  async postWithRetry(url, payload, { timeout = 15000, retries = 2, baseDelay = 300 } = {}) {
    let attempt = 0;
    let lastErr;

    while (attempt <= retries) {
      try {
        return await this.client.post(url, payload, { timeout });
      } catch (err) {
        lastErr = err;
        const msg = err?.message || '';

        // Determinar si el error es recuperable
        const retriable = /ENOTFOUND|ECONNRESET|ETIMEDOUT|EAI_AGAIN|timeout/i.test(msg);

        if (!retriable || attempt === retries) {
          throw err;
        }

        // Calcular delay con backoff exponencial
        const delay = baseDelay * Math.pow(2, attempt);
        console.warn(`HTTP retry ${attempt + 1}/${retries} en ${delay}ms: ${msg}`);
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
