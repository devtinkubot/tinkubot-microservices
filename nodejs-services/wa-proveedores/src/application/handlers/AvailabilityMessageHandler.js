/**
 * AvailabilityMessageHandler.js
 * Handler especializado para respuestas de disponibilidad de proveedores
 *
 * Responsabilidad:
 * - Detectar y procesar respuestas a solicitudes de disponibilidad (1 o 2)
 * - Coordinar con MqttClient para registrar respuestas
 * - Manejar expiración y cupos máximos
 * - Notificar al proveedor sobre el resultado
 */

const BaseMessageHandler = require('./BaseMessageHandler');

/**
 * Clase AvailabilityMessageHandler
 * Maneja respuestas de disponibilidad de proveedores
 */
class AvailabilityMessageHandler extends BaseMessageHandler {
  /**
   * @param {MessageSenderWithRetry} messageSender - Sender de mensajes WhatsApp
   * @param {AIServiceClient} aiServiceClient - Cliente del AI Service
   * @param {MqttClient} mqttClient - Cliente MQTT para gestionar disponibilidad
   */
  constructor(messageSender, aiServiceClient, mqttClient) {
    super(messageSender, aiServiceClient);
    if (!mqttClient) {
      throw new Error('mqttClient is required for AvailabilityMessageHandler');
    }
    this.mqttClient = mqttClient;
  }

  /**
   * Determina si este handler puede procesar el mensaje
   * @param {object} message - Mensaje de WhatsApp
   * @returns {boolean} true si hay una solicitud activa para este número
   */
  canHandle(message) {
    // Solo manejar si hay una solicitud activa para este teléfono
    const solicitud = this.mqttClient.getActiveRequest(message.from);
    return solicitud !== null;
  }

  /**
   * Procesa la respuesta de disponibilidad
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<void>}
   */
  async handle(message) {
    const opcion = (message.body || '').trim().toLowerCase();
    const chat = await message.getChat();

    // Procesar la respuesta a través de MQTT
    const result = this.mqttClient.processAvailabilityResponse(message.from, opcion);

    if (!result.handled) {
      // No debería llegar aquí por el check de canHandle, pero por seguridad
      console.warn(`⚠️ No hay solicitud activa para ${message.from}`);
      return;
    }

    // Manejar expiración
    if (result.expired) {
      await chat.sendMessage(
        '*El tiempo de respuesta ha caducado y tu respuesta ya no contará para este requerimiento.*'
      );
      return;
    }

    // Manejar cupo lleno
    if (result.full) {
      await chat.sendMessage('*Las plazas para este requerimiento ya han sido ocupadas.*');
      return;
    }

    // Respuesta aceptada
    if (result.accepted) {
      const reqId = this.mqttClient.getActiveRequest(message.from)?.reqId;
      await chat.sendMessage('*Gracias, tomamos nota de tu disponibilidad.*');

      // Verificar si se llenó el cupo después de esta respuesta
      if (result.count >= this.mqttClient.config.maxResponses) {
        await this._notifyRemainingProviders(reqId);
      }
      return;
    }

    // Respuesta declinada
    await chat.sendMessage('*Entendido, registramos que no estás disponible para esta solicitud.*');
  }

  /**
   * Notifica a los proveedores pendientes que el cupo se llenó
   * @private
   * @param {string} reqId - ID del requerimiento
   * @returns {Promise<void>}
   */
  async _notifyRemainingProviders(reqId) {
    if (!reqId) return;

    const phones = Array.from(this.mqttClient.getRequestPhones(reqId));
    if (phones.length === 0) return;

    for (const phone of phones) {
      try {
        await this.messageSender.sendText(
          phone,
          '*Las plazas para este requerimiento ya han sido ocupadas.*'
        );
      } catch (err) {
        console.error(`❌ No se pudo notificar cierre de cupo a ${phone}:`, err.message || err);
      }
    }
  }
}

module.exports = AvailabilityMessageHandler;
