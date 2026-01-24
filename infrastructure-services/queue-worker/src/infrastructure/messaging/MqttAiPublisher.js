/**
 * MqttAiPublisher.js
 * Publica mensajes a ai-clientes vía MQTT
 *
 * Responsabilidad:
 * - Publicar mensajes en el topic ai-clientes/process
 * - Reemplaza las llamadas HTTP POST a /handle-whatsapp-message
 *
 * MQTT-First Architecture:
 * Flujo: Worker → MQTT (ai-clientes/process) → ai-clientes MQTT Subscriber
 */

const crypto = require('crypto');

class MqttAiPublisher {
  /**
   * @param {MqttClient} mqttClient - Cliente MQTT para publicar mensajes
   * @param {object} options - Opciones adicionales
   */
  constructor(mqttClient, options = {}) {
    this._mqttClient = mqttClient;
    this._topic = options.topic || process.env.MQTT_TEMA_AI_CLIENTES_PROCESS || 'ai-clientes/process';
    this._qos = options.qos || 1;
  }

  /**
   * Publica un mensaje en el topic ai-clientes/process
   * @param {object} messageData - Datos del mensaje de WhatsApp
   * @returns {Promise<void>}
   */
  async publishMessage(messageData) {
    if (!this._mqttClient.isConnected()) {
      throw new Error('[MqttAiPublisher] MQTT Client no conectado');
    }

    // Extraer datos del mensaje
    const from = messageData.from || messageData.from_number;
    const content = messageData.body || messageData.content || '';

    // Construir payload MQTT según estándar
    const mqttPayload = {
      message_id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      source_service: 'wa-clientes-worker',
      type: 'whatsapp_message',
      payload: {
        from_number: from,
        content: content,
        message_type: messageData.type || 'chat',
        timestamp: messageData.timestamp || Date.now(),
        message_id: messageData.id,
        location: messageData.location || null,
      }
    };

    return new Promise((resolve, reject) => {
      this._mqttClient.client.publish(
        this._topic,
        JSON.stringify(mqttPayload),
        { qos: this._qos },
        (err) => {
          if (err) {
            console.error(
              `[MqttAiPublisher] Error publicando en ${this._topic}:`,
              err.message
            );
            reject(err);
          } else {
            console.debug(
              `[MqttAiPublisher] Mensaje publicado en ${this._topic} para ${from}`
            );
            resolve();
          }
        }
      );
    });
  }

  /**
   * Verifica si el MQTT Client está conectado
   * @returns {boolean} True si está conectado
   */
  isConnected() {
    return this._mqttClient.isConnected();
  }
}

module.exports = MqttAiPublisher;
