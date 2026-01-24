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

const mqtt = require("mqtt");

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
   * @param {object} options - Opciones de conexión
   * @param {boolean} options.autoSubscribe - Suscribirse automáticamente a topics (default: true)
   */
  connect(options = {}) {
    const { autoSubscribe = true } = options;

    try {
      const { host, port, username, password, topicWhatsappSend } = this.config;
      const url = `mqtt://${host}:${port}`;
      const mqttOptions = {};

      if (username && password) {
        mqttOptions.username = username;
        mqttOptions.password = password;
      }

      this.client = mqtt.connect(url, mqttOptions);

      this.client.on("connect", () => {
        console.warn(`📡 MQTT conectado a ${url}`);

        // Solo suscribirse si autoSubscribe es true (para Producer)
        if (autoSubscribe && this.whatsappClient) {
          this.client.subscribe(topicWhatsappSend, (err) => {
            if (err) {
              console.error(
                "❌ No se pudo suscribir a whatsapp/send:",
                err.message || err,
              );
            } else {
              console.warn(`✅ Suscrito a ${topicWhatsappSend} (MQTT Fase 1)`);
            }
          });
        } else if (!autoSubscribe) {
          console.warn(`📤 MQTT en modo publicación única (Worker)`);
        }
      });

      this.client.on("error", (err) => {
        console.error("❌ Error MQTT:", err.message || err);
      });

      // Solo configurar handler de mensajes si hay whatsappClient
      if (this.whatsappClient) {
        this.client.on("message", async (topic, message) => {
          try {
            await this._handleMessage(topic, message);
          } catch (err) {
            console.error(
              "❌ Error procesando mensaje MQTT:",
              err.message || err,
            );
          }
        });
      }
    } catch (err) {
      console.error("❌ No se pudo inicializar MQTT:", err.message || err);
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
    if (raw.endsWith("@c.us") || raw.endsWith("@g.us") || raw.endsWith("@lid"))
      return raw;

    const soloDigitos = raw.replace(/[^\d]/g, "");
    if (!soloDigitos) return null;

    let normalizado = soloDigitos;
    if (normalizado.startsWith("0")) {
      normalizado = normalizado.replace(/^0+/, "");
    }
    if (normalizado.startsWith("593")) {
      normalizado = normalizado.replace(/^593+/, "593");
    } else if (normalizado.length === 9 && normalizado.startsWith("9")) {
      normalizado = `593${normalizado}`;
    }

    if (!normalizado.startsWith("593")) {
      console.warn(
        `⚠️ Número sin prefijo de país, se usa tal cual: ${normalizado}`,
      );
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
      console.error("❌ Error parseando JSON MQTT:", err.message);
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
   *
   * Formato esperado del payload:
   * {
   *   phone: "593959091325@c.us",
   *   message: {
   *     template: "providers_results",
   *     response: "✅ Mensaje formateado desde Python...",  // PRIORIDAD
   *     data: { city: "Cuenca", providers: [...] }
   *   }
   * }
   */
  async _handleWhatsappSend(mqttMessage) {
    // Extraer payload del estándar MQTTMessage
    // Formato: { message_id, timestamp, source_service, type, payload: { to, message } }
    const payload = mqttMessage?.payload || mqttMessage; // Fallback por compatibilidad

    const phone = payload?.to || payload?.phone;
    const messageContent = payload?.message;

    if (!phone || !messageContent) {
      console.warn(
        "⚠️ Mensaje MQTT whatsapp/send sin phone/message en payload, se ignora:",
        mqttMessage,
      );
      return;
    }

    try {
      // Normalizar número
      const normalizedPhone = this._normalizeWhatsAppNumber(phone);

      let formattedMessage;

      // ============================================
      // UNICA PRIORIDAD: 'response' desde Python
      // ============================================
      if (typeof messageContent === "object" && messageContent.response) {
        formattedMessage = messageContent.response;
        console.debug(`✅ Usando mensaje formateado desde Python (response field)`);
      } else {
        console.error(
          `❌ Mensaje MQTT sin campo 'response'. Data: ${JSON.stringify(messageContent)}`
        );
        formattedMessage = "❌ Error interno: mensaje mal formateado.";
      }

      // Enviar mensaje formateado por WhatsApp
      await this.whatsappClient.sendMessage(normalizedPhone, formattedMessage);

      console.warn(
        `✅ Mensaje WhatsApp enviado vía MQTT a ${phone} (topic=whatsapp/clientes/send)`,
      );
    } catch (err) {
      console.error(
        `❌ Error enviando mensaje WhatsApp vía MQTT a ${phone}:`,
        err.message || err,
      );
    }
  }

  /**
   * Verifica si el cliente está conectado
   * @returns {boolean} True si está conectado
   */
  isConnected() {
    return this.client && this.client.connected;
  }

  /**
   * Publica un mensaje en un topic MQTT
   * Usado por el Worker para enviar respuestas que el Producer entregará
   * @param {string} phone - Número de teléfono destino
   * @param {string} message - Mensaje a enviar
   * @returns {Promise<void>}
   */
  async publishResponse(phone, message) {
    if (!this.isConnected()) {
      throw new Error("[MqttClient] No conectado a MQTT");
    }

    const { topicWhatsappSend } = this.config;

    // Formato estándar MQTTMessage
    const mqttMessage = {
      message_id: `worker-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      source_service: "wa-clientes-worker",
      type: "whatsapp_send",
      payload: {
        to: phone,
        message: message,
      },
    };

    return new Promise((resolve, reject) => {
      this.client.publish(
        topicWhatsappSend,
        JSON.stringify(mqttMessage),
        { qos: 1 },
        (err) => {
          if (err) {
            console.error(
              `[MqttClient] Error publicando en ${topicWhatsappSend}:`,
              err.message,
            );
            reject(err);
          } else {
            console.debug(
              `[MqttClient] Mensaje publicado en ${topicWhatsappSend} para ${phone}`,
            );
            resolve();
          }
        },
      );
    });
  }
}

module.exports = MqttClient;
