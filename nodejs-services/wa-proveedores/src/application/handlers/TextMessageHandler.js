/**
 * TextMessageHandler.js
 * Handler para mensajes de texto y ubicación (Strategy Pattern)
 *
 * Responsabilidad:
 * - Manejar mensajes de texto, ubicación y live_location
 * - Procesar mensajes con el AI Service
 * - Enviar respuestas estructuradas (botones, media, etc.)
 */

const BaseMessageHandler = require('./BaseMessageHandler');

/**
 * Clase TextMessageHandler
 * Maneja mensajes de texto y ubicación
 */
class TextMessageHandler extends BaseMessageHandler {
  /**
   * Determina si este handler puede procesar el mensaje
   * @param {object} message - Mensaje de WhatsApp
   * @returns {boolean} true si el mensaje es de tipo conversacional
   */
  canHandle(message) {
    const allowedTypes = new Set(['chat', 'image', 'location', 'live_location']);
    return allowedTypes.has(message.type);
  }

  /**
   * Procesa el mensaje
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<void>}
   */
  async handle(message) {
    const instanceName = message.constructor.name === 'Object' ? 'WhatsAppClient' : 'Client';

    // Logging del mensaje recibido
    console.warn(
      `[${instanceName}] Mensaje recibido de ${message.from}:`,
      message.body || '[Mensaje sin texto]'
    );
    console.warn('  tipo:', message.type, 'tieneUbicacion:', !!message.location);

    // Depuración avanzada para ubicaciones
    if (message.type === 'location' || message.type === 'live_location') {
      this._logLocationDetails(message);
    }

    // Log de quoted message si existe
    if (message.hasQuotedMsg) {
      await this._logQuotedMessage(message);
    }

    // Ignorar mensajes de broadcast y del sistema
    if (this._shouldIgnoreMessage(message)) {
      return;
    }

    // Procesar con IA y responder
    try {
      const ai = await this.processWithAI(message);

      try {
        console.warn('AI raw:', JSON.stringify(ai).slice(0, 500));
      } catch {}

      // Permitir múltiples mensajes en una sola respuesta de IA
      if (Array.isArray(ai.messages) && ai.messages.length > 0) {
        for (const m of ai.messages) {
          await this.sendResponse(message.from, m || {});
        }
      } else {
        await this.sendResponse(message.from, ai || {});
      }
    } catch (error) {
      await this.sendError(message.from, error);
    }
  }

  /**
   * Verifica si el mensaje debe ser ignorado
   * @private
   * @param {object} message - Mensaje de WhatsApp
   * @returns {boolean} true si el mensaje debe ser ignorado
   */
  _shouldIgnoreMessage(message) {
    return (
      message.from === 'status@broadcast' ||
      message.from.endsWith('@g.us') ||
      message.from.endsWith('@broadcast')
    );
  }

  /**
   * Registra detalles de ubicación para debugging
   * @private
   * @param {object} message - Mensaje de WhatsApp
   */
  _logLocationDetails(message) {
    console.warn('🔍 Detalles del mensaje de ubicación:');
    console.warn('  - type:', message.type);
    console.warn('  - hasMedia:', message.hasMedia);
    console.warn('  - location type:', typeof message.location);
    if (message.location) {
      console.warn('  - location keys:', Object.keys(message.location));
      console.warn('  - location completo:', JSON.stringify(message.location, null, 2));
    }
    console.warn('  - body length:', message.body ? message.body.length : 0);
    console.warn(
      '  - body preview:',
      message.body ? message.body.substring(0, 100) + '...' : '[none]'
    );
  }

  /**
   * Registra el quoted message para debugging
   * @private
   * @param {object} message - Mensaje de WhatsApp
   */
  async _logQuotedMessage(message) {
    try {
      const quoted = await message.getQuotedMessage();
      console.warn('  quoted body:', quoted && quoted.body ? quoted.body : '[none]');
    } catch {
      // Ignorar errores al obtener quoted message
    }
  }
}

module.exports = TextMessageHandler;
