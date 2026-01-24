/**
 * MessageSenderWithRetry.js
 * Manejo de envío de mensajes WhatsApp con lógica de reintentos
 *
 * Responsabilidad:
 * - Enviar mensajes de texto con reintentos automáticos
 * - Enviar mensajes multimedia con reintentos
 * - Enviar botones y resultados de proveedores
 * - Implementar backoff exponencial para reintentos
 */

const { MessageMedia } = require('whatsapp-web.js');

/**
 * Clase MessageSenderWithRetry
 * Maneja el envío de mensajes con lógica de reintentos
 */
class MessageSenderWithRetry {
  /**
   * @param {Client} whatsappClient - Cliente de WhatsAppWeb.js
   */
  constructor(whatsappClient) {
    this.client = whatsappClient;
  }

  /**
   * Actualiza el cliente de WhatsApp (útil si el cliente se reinicia)
   * @param {Client} whatsappClient - Nuevo cliente de WhatsApp
   */
  setClient(whatsappClient) {
    this.client = whatsappClient;
  }

  /**
   * Envío con reintentos y backoff exponencial
   * @param {Function} sendFn - Función de envío a ejecutar
   * @param {number} maxRetries - Máximo número de reintentos (default: 3)
   * @param {number} baseDelayMs - Delay base en ms (default: 300)
   * @returns {Promise<Result>} Resultado del envío
   */
  async sendWithRetry(sendFn, maxRetries = 3, baseDelayMs = 300) {
    let attempt = 0;
    let lastErr;

    while (attempt <= maxRetries) {
      try {
        return await sendFn();
      } catch (err) {
        lastErr = err;
        const msg = (err && (err.message || err.originalMessage)) || '';

        // Determinar si el error es recuperable (errores típicos de Puppeteer)
        const retriable =
          /Execution context was destroyed|Target closed|Evaluation failed|Protocol error/i.test(msg);

        if (!retriable || attempt === maxRetries) {
          console.error('sendWithRetry: fallo definitivo:', msg);
          throw err;
        }

        // Calcular delay con backoff exponencial
        const delay = baseDelayMs * Math.pow(2, attempt);
        console.warn(
          `sendWithRetry: reintentando en ${delay}ms (intento ${attempt + 1}/${maxRetries})`
        );
        await new Promise(r => setTimeout(r, delay));
        attempt++;
      }
    }

    throw lastErr;
  }

  /**
   * Envía un mensaje de texto
   * @param {string} to - Número de destino
   * @param {string} text - Texto a enviar
   * @returns {Promise<Result>} Resultado del envío
   */
  async sendText(to, text) {
    const safeText = text || ' ';
    return this.sendWithRetry(() => this.client.sendMessage(to, safeText));
  }

  /**
   * Envía botones (opciones numeradas)
   * @param {string} to - Número de destino
   * @param {string} text - Texto a enviar con las instrucciones
   * @returns {Promise<Result>} Resultado del envío
   */
  async sendButtons(to, text) {
    await this.sendText(to, text || 'Responde con el número de tu opción:');
  }

  /**
   * Envía resultados de proveedores
   * @param {string} to - Número de destino
   * @param {string} text - Texto con instrucciones
   * @returns {Promise<Result>} Resultado del envío
   */
  async sendProviderResults(to, text) {
    // No añadir menú numérico aquí; ai-clientes ya envía la instrucción adecuada.
    await this.sendText(to, text || ''); // texto ya viene con la instrucción a-e
  }

  /**
   * Envía un mensaje multimedia (imagen, video, documento)
   * @param {string} to - Número de destino
   * @param {string} mediaUrl - URL del archivo multimedia
   * @param {string} caption - Texto descriptivo opcional
   * @returns {Promise<Result>} Resultado del envío
   */
  async sendMedia(to, mediaUrl, caption) {
    if (!mediaUrl) return;

    const media = await MessageMedia.fromUrl(mediaUrl, { unsafeMime: true });
    const options = caption ? { caption } : {};

    return this.sendWithRetry(() => this.client.sendMessage(to, media, options));
  }

  /**
   * Obtiene el cliente de WhatsApp actual
   * @returns {Client} Cliente de WhatsApp
   */
  getClient() {
    return this.client;
  }
}

module.exports = MessageSenderWithRetry;
