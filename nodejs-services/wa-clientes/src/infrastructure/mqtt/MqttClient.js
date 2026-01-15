/**
 * MqttClient.js
 * Cliente MQTT para wa-clientes
 *
 * Responsabilidad:
 * - Conectar y gestionar conexión MQTT
 * - Suscribirse a temas de envío de mensajes WhatsApp
 * - Manejar mensajes MQTT para enviar WhatsApp
 *
 * MQTT MIGRATION Fase 1:
 * - Suscripción a whatsapp/clientes/send
 * - Reemplazo de HTTP endpoint /send por MQTT
 */

const mqtt = require('mqtt');

/**
 * Clase MqttClient
 * Maneja la comunicación MQTT para enviar mensajes WhatsApp
 */
class MqttClient {
  /**
   * @param {object} mqttConfig - Configuración MQTT
   * @param {object} whatsappClient - Cliente de WhatsApp para enviar mensajes
   */
  constructor(mqttConfig, whatsappClient) {
    this.config = mqttConfig;
    this.whatsappClient = whatsappClient;
    this.client = null;
  }

  /**
   * Conecta al broker MQTT y configura suscripciones
   */
  connect() {
    try {
      const { host, port, username, password, topicWhatsappSend } = this.config;
      const url = `mqtt://${host}:${port}`;
      const options = {};

      if (username && password) {
        options.username = username;
        options.password = password;
      }

      this.client = mqtt.connect(url, options);

      this.client.on('connect', () => {
        console.warn(`📡 MQTT conectado a ${url}`);

        // Suscribirse a topic de envío de mensajes
        this.client.subscribe(topicWhatsappSend, err => {
          if (err) {
            console.error('❌ No se pudo suscribir a whatsapp/send:', err.message || err);
          } else {
            console.warn(`✅ Suscrito a ${topicWhatsappSend} (MQTT Fase 1)`);
          }
        });
      });

      this.client.on('error', err => {
        console.error('❌ Error MQTT:', err.message || err);
      });

      this.client.on('message', async (topic, message) => {
        try {
          await this._handleMessage(topic, message);
        } catch (err) {
          console.error('❌ Error procesando mensaje MQTT:', err.message || err);
        }
      });
    } catch (err) {
      console.error('❌ No se pudo inicializar MQTT:', err.message || err);
    }
  }

  /**
   * Normaliza un número de WhatsApp
   * @private
   * @param {string} numero - Número a normalizar
   * @returns {string|null} Número normalizado o null si es inválido
   */
  _normalizeWhatsAppNumber(numero) {
    if (!numero) return null;
    const raw = String(numero).trim();
    if (raw.endsWith('@c.us') || raw.endsWith('@g.us') || raw.endsWith('@lid')) return raw;

    const soloDigitos = raw.replace(/[^\d]/g, '');
    if (!soloDigitos) return null;

    let normalizado = soloDigitos;
    if (normalizado.startsWith('0')) {
      normalizado = normalizado.replace(/^0+/, '');
    }
    if (normalizado.startsWith('593')) {
      normalizado = normalizado.replace(/^593+/, '593');
    } else if (normalizado.length === 9 && normalizado.startsWith('9')) {
      normalizado = `593${normalizado}`;
    }

    if (!normalizado.startsWith('593')) {
      console.warn(`⚠️ Número sin prefijo de país, se usa tal cual: ${normalizado}`);
    }

    return `${normalizado}@c.us`;
  }

  /**
   * Maneja mensajes entrantes de MQTT
   * @private
   * @param {string} topic - Tema del mensaje
   * @param {Buffer} message - Contenido del mensaje
   */
  async _handleMessage(topic, message) {
    const { topicWhatsappSend } = this.config;

    // Parsear mensaje según estándar MQTTMessage
    let data;
    try {
      data = JSON.parse(message.toString());
    } catch (err) {
      console.error('❌ Error parseando JSON MQTT:', err.message);
      return;
    }

    if (topic === topicWhatsappSend) {
      await this._handleWhatsappSend(data);
      return;
    }
  }

  /**
   * Maneja envío de mensajes WhatsApp vía MQTT (Fase 1)
   * @private
   * @param {object} mqttMessage - Mensaje MQTT según estándar MQTTMessage
   */
  async _handleWhatsappSend(mqttMessage) {
    // Extraer payload del estándar MQTTMessage
    // Formato: { message_id, timestamp, source_service, type, payload: { to, message } }
    const payload = mqttMessage?.payload || mqttMessage; // Fallback por compatibilidad

    const phone = payload?.to || payload?.phone;
    const message = payload?.message;

    if (!phone || !message) {
      console.warn('⚠️ Mensaje MQTT whatsapp/send sin to/message en payload, se ignora:', mqttMessage);
      return;
    }

    try {
      // Normalizar número y enviar
      const normalizedPhone = this._normalizeWhatsAppNumber(phone);
      const contenido = message || ' ';

      await this.whatsappClient.sendMessage(normalizedPhone, contenido);

      console.warn(`✅ Mensaje WhatsApp enviado vía MQTT a ${phone} (topic=whatsapp/clientes/send)`);
    } catch (err) {
      console.error(`❌ Error enviando mensaje WhatsApp vía MQTT a ${phone}:`, err.message || err);
    }
  }

  /**
   * Verifica si el cliente está conectado
   * @returns {boolean} True si está conectado
   */
  isConnected() {
    return this.client && this.client.connected;
  }
}

module.exports = MqttClient;
