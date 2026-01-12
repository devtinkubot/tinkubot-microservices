/**
 * AIServiceClient.js
 * Cliente para comunicarse con el AI Service
 *
 * Responsabilidad:
 * - Enviar mensajes al AI Service para procesamiento
 * - Construir payloads enriquecidos con contexto del mensaje
 * - Manejar errores de comunicación con el AI Service
 */

const axiosClient = require('../../infrastructure/http/axiosClient');

/**
 * Clase AIServiceClient
 * Maneja la comunicación con el servicio de IA
 */
class AIServiceClient {
  /**
   * @param {string} aiServiceUrl - URL base del AI Service
   */
  constructor(aiServiceUrl) {
    this.aiServiceUrl = aiServiceUrl;
  }

  /**
   * Procesa un mensaje de WhatsApp a través del AI Service
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<object>} Respuesta del AI Service
   */
  async processMessage(message) {
    try {
      const payload = await this._buildPayload(message);
      const response = await axiosClient.postWithRetry(
        `${this.aiServiceUrl}/handle-whatsapp-message`,
        payload,
        {
          timeout: 20000, // acortar para no bloquear el loop
          retries: 0, // evitar duplicar solicitudes en casos de espera larga
        }
      );
      return response.data;
    } catch (error) {
      return this._handleError(error);
    }
  }

  /**
   * Construye el payload para enviar al AI Service
   * @private
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<object>} Payload enriquecido
   */
  async _buildPayload(message) {
    const payload = {
      id: message.id._serialized || message.id,
      from_number: message.from,
      content: message.body || '',
      timestamp: message.timestamp
        ? new Date(message.timestamp * 1000).toISOString()
        : new Date().toISOString(),
      status: 'received',
      message_type: message.type,
      message_id: message.id._serialized || message.id || '',
      device_type: message.deviceType || ''
    };

    // Selección por reply-to: si responde citando una opción, usar el texto citado como selected_option
    if (message.hasQuotedMsg) {
      try {
        const quoted = await message.getQuotedMessage();
        if (quoted && quoted.body) {
          payload.selected_option = quoted.body.trim();
        }
      } catch (e) {
        console.warn('No se pudo obtener quoted message:', e.message || e);
      }
    }

    // Ubicación compartida - Manejo mejorado según documentación oficial de WhatsApp Web.js
    if ((message.type === 'location' || message.type === 'live_location') && message.location) {
      console.warn('📍 Objeto location completo:', JSON.stringify(message.location, null, 2));

      // Según documentación oficial, Location tiene propiedades: latitude, longitude, name, address, url
      const lat = message.location.latitude;
      const lng = message.location.longitude;

      console.warn('📍 Coordenadas extraídas - lat:', lat, 'lng:', lng);

      if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
        payload.location = {
          lat: parseFloat(lat),
          lng: parseFloat(lng),
          name: message.location.name || undefined,
          address: message.location.address || undefined,
        };
        console.warn('✅ Ubicación válida procesada:', payload.location);
      } else {
        console.warn('❌ Coordenadas inválidas - lat:', lat, 'lng:', lng);
      }
    }

    // Solo adjuntar ubicación cuando sea mensaje de ubicación nativo
    if (payload.location) {
      console.warn('✅ Ubicación detectada desde objeto location nativo');
    }

    // Manejo de imágenes y media - EXTRAER IMÁGENES PARA REGISTRO DE PROVEEDORES
    if (message.hasMedia) {
      try {
        const media = await message.downloadMedia();
        if (media && media.mimetype && media.mimetype.startsWith('image/')) {
          payload.image_base64 = media.data;
          payload.mime_type = media.mimetype;
          console.warn('✅ Imagen extraída del mensaje:', media.mimetype, 'tamaño:', media.data.length, 'bytes');
        } else if (media) {
          console.warn('⚠️ Media no es imagen, mimetype:', media.mimetype || 'desconocido');
        }
      } catch (error) {
        console.error('❌ Error descargando media del mensaje:', error.message);
        // No fallar el flujo por errores de descarga de media
      }
    }

    return payload;
  }

  /**
   * Maneja errores de comunicación con el AI Service
   * @private
   * @param {Error} error - Error capturado
   * @returns {object} Respuesta de fallback
   */
  _handleError(error) {
    if (error.response) {
      console.error('Error IA status:', error.response.status, error.response.data);
    } else {
      console.error('Error al procesar con IA:', error.message || error);
    }

    if (error.response && error.response.status === 400) {
      return {
        text: 'Lo siento, no pude procesar tu mensaje. Por favor, intenta enviar un mensaje de texto claro.',
      };
    }

    return { text: 'Lo siento, estoy teniendo problemas para procesar tu mensaje.' };
  }

  /**
   * Verifica la salud del AI Service
   * @returns {Promise<boolean>} true si el servicio está saludable
   */
  async healthCheck() {
    try {
      const response = await axiosClient.get(`${this.aiServiceUrl}/health`, {
        timeout: 5000,
      });
      return response.data && response.data.status === 'ok';
    } catch (error) {
      console.error('AI Service health check failed:', error.message);
      return false;
    }
  }
}

module.exports = AIServiceClient;
