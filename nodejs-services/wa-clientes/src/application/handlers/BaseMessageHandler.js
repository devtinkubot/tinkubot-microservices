/**
 * BaseMessageHandler.js
 * Clase base para handlers de mensajes de WhatsApp (Strategy Pattern)
 *
 * Responsabilidad:
 * - Definir interfaz común para todos los handlers
 * - Implementar métodos compartidos de procesamiento de respuestas AI
 * - Proporcionar estructura para el Strategy Pattern
 */

const AIServiceClient = require('../services/AIServiceClient');

/**
 * Clase BaseMessageHandler
 * Base abstracta para todos los handlers de mensajes
 */
class BaseMessageHandler {
  /**
   * @param {MessageSenderWithRetry} messageSender - Sender de mensajes WhatsApp
   * @param {AIServiceClient} aiServiceClient - Cliente del AI Service
   */
  constructor(messageSender, aiServiceClient) {
    if (!messageSender || !aiServiceClient) {
      throw new Error('messageSender and aiServiceClient are required');
    }
    this.messageSender = messageSender;
    this.aiServiceClient = aiServiceClient;
  }

  /**
   * Determina si este handler puede procesar el mensaje
   * @param {object} message - Mensaje de WhatsApp
   * @returns {boolean} true si este handler puede procesar el mensaje
   */
  canHandle(message) {
    throw new Error('canHandle must be implemented by subclass');
  }

  /**
   * Procesa el mensaje
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<void>}
   */
  async handle(message) {
    throw new Error('handle must be implemented by subclass');
  }

  /**
   * Procesa un mensaje con el AI Service
   * @protected
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<object>} Respuesta del AI Service
   */
  async processWithAI(message) {
    return await this.aiServiceClient.processMessage(message);
  }

  /**
   * Envía una respuesta de IA al usuario
   * @protected
   * @param {string} to - Número de destino
   * @param {object} aiResponse - Respuesta del AI Service
   * @returns {Promise<void>}
   */
  async sendResponse(to, aiResponse) {
    const text = aiResponse.ai_response || aiResponse.response || aiResponse.text;
    const ui = aiResponse.ui || {};
    const mediaUrl = aiResponse.media_url || aiResponse.image_url || (aiResponse.media && aiResponse.media.url);
    const mediaCaption = aiResponse.media_caption || aiResponse.caption || text;
    let mediaSent = false;

    // Enviar media si existe
    if (mediaUrl) {
      try {
        await this.messageSender.sendMedia(to, mediaUrl, mediaCaption);
        mediaSent = true;
      } catch (err) {
        console.error('No se pudo enviar la foto (media):', err?.message || err);
      }
    }

    // Manejar diferentes tipos de UI
    if (ui.type === 'buttons' && Array.isArray(ui.buttons)) {
      await this.messageSender.sendButtons(to, text || 'Elige una opción:');
      console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
      return;
    }

    if (ui.type === 'location_request') {
      await this.messageSender.sendText(
        to,
        text || 'Por favor comparte tu ubicación 📎 para mostrarte los más cercanos.'
      );
      console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
      return;
    }

    if (ui.type === 'provider_results') {
      try {
        const names = (ui.providers || []).map(p => p.name || 'Proveedor');
        console.warn('➡️ Enviando provider_results al usuario:', { count: names.length, names });
      } catch {}
      await this.messageSender.sendProviderResults(to, text || 'Encontré estas opciones:');
      console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
      return;
    }

    if (ui.type === 'feedback' && Array.isArray(ui.options)) {
      await this.messageSender.sendButtons(to, text || 'Califica tu experiencia:');
      console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
      return;
    }

    if (ui.type === 'silent') {
      return;
    }

    // Fallback: enviar texto si hay media y el caption es diferente
    if (mediaSent && (!text || mediaCaption === text)) {
      console.warn('Respuesta enviada (IA): media');
      return;
    }

    if (mediaSent && text && mediaCaption !== text) {
      await this.messageSender.sendText(to, text);
      console.warn('Respuesta enviada (IA): media + texto');
      return;
    }

    if (text) {
      await this.messageSender.sendText(to, text);
      console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
    } else {
      await this.messageSender.sendText(to, 'Procesando tu mensaje...');
      console.warn('Respuesta enviada (IA): procesamiento');
    }
  }

  /**
   * Envía un mensaje de error al usuario
   * @protected
   * @param {string} to - Número de destino
   * @param {Error} error - Error capturado
   * @returns {Promise<void>}
   */
  async sendError(to, error) {
    console.error('Error al procesar mensaje:', error);
    await this.messageSender.sendText(
      to,
      'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.'
    );
  }
}

module.exports = BaseMessageHandler;
