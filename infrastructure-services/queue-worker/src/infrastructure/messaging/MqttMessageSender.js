/**
 * MqttMessageSender.js
 * Envía mensajes de WhatsApp vía MQTT
 *
 * Responsabilidad:
 * - Publicar mensajes en MQTT para que el Producer los envíe
 * - Usado por el Worker en lugar de enviar directamente a WhatsApp
 *
 * Fase 1: Estabilización Crítica
 * Flujo: Worker → MQTT → Producer → WhatsApp
 */

class MqttMessageSender {
  /**
   * @param {MqttClient} mqttClient - Cliente MQTT para publicar mensajes
   */
  constructor(mqttClient) {
    this._mqttClient = mqttClient;
  }

  /**
   * Envía un mensaje de texto vía MQTT
   * @param {string} to - Número de teléfono destino
   * @param {string} message - Mensaje a enviar
   * @returns {Promise<void>}
   */
  async sendText(to, message) {
    if (!this._mqttClient.isConnected()) {
      throw new Error('[MqttMessageSender] MQTT Client no conectado');
    }

    await this._mqttClient.publishResponse(to, message);
  }

  /**
   * Verifica si el MQTT Client está conectado
   * @returns {boolean} True si está conectado
   */
  isConnected() {
    return this._mqttClient.isConnected();
  }
}

module.exports = MqttMessageSender;
