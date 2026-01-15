/**
 * MqttClient.js
 * Cliente MQTT para gestión de disponibilidad de proveedores
 *
 * Responsabilidad:
 * - Conectar y gestionar conexión MQTT
 * - Suscribirse a temas de solicitudes de disponibilidad
 * - Publicar respuestas de disponibilidad
 * - Manejar eventos de aprobación/rechazo de proveedores
 * - Gestionar estado de solicitudes activas con expiración
 */

const mqtt = require('mqtt');

/**
 * Clase MqttClient
 * Maneja la comunicación MQTT para el sistema de disponibilidad
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

    // Estado de solicitudes activas
    // solicitudesActivas: providerPhone -> { reqId, providerId, expiresAt, timer }
    this.solicitudesActivas = new Map();
    // solicitudesPorReq: reqId -> Set(providerPhone)
    this.solicitudesPorReq = new Map();
    // respuestasPorReq: reqId -> count de aceptadas
    this.respuestasPorReq = new Map();

    this.messageHandler = null; // Handler para mensajes de disponibilidad
  }

  /**
   * Establece el handler para mensajes de respuesta de disponibilidad
   * @param {Function} handler - Función handler(message, solicitud)
   */
  setAvailabilityHandler(handler) {
    this.messageHandler = handler;
  }

  /**
   * Conecta al broker MQTT y configura suscripciones
   */
  connect() {
    try {
      const { host, port, username, password } = this.config;
      const url = `mqtt://${host}:${port}`;
      const options = {};

      if (username && password) {
        options.username = username;
        options.password = password;
      }

      this.client = mqtt.connect(url, options);

      this.client.on('connect', () => {
        console.warn(`📡 MQTT conectado a ${url}`);
        this._setupSubscriptions();
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
   * Configura las suscripciones a temas MQTT
   * @private
   */
  _setupSubscriptions() {
    const { topicRequest, topicApproved, topicRejected, topicWhatsappSend } = this.config;

    this.client.subscribe(topicRequest, err => {
      if (err) {
        console.error('❌ No se pudo suscribir a solicitudes:', err.message || err);
      } else {
        console.warn(`✅ Suscrito a ${topicRequest}`);
      }
    });

    this.client.subscribe(topicApproved, err => {
      if (err) {
        console.error('❌ No se pudo suscribir a aprobaciones:', err.message || err);
      } else {
        console.warn(`✅ Suscrito a ${topicApproved}`);
      }
    });

    this.client.subscribe(topicRejected, err => {
      if (err) {
        console.error('❌ No se pudo suscribir a rechazos:', err.message || err);
      } else {
        console.warn(`✅ Suscrito a ${topicRejected}`);
      }
    });

    // MQTT MIGRATION Fase 1: Suscribirse a topic de envío de mensajes
    this.client.subscribe(topicWhatsappSend, err => {
      if (err) {
        console.error('❌ No se pudo suscribir a whatsapp/send:', err.message || err);
      } else {
        console.warn(`✅ Suscrito a ${topicWhatsappSend} (MQTT Fase 1)`);
      }
    });
  }

  /**
   * Maneja mensajes entrantes de MQTT
   * @private
   * @param {string} topic - Tema del mensaje
   * @param {Buffer} message - Contenido del mensaje
   */
  async _handleMessage(topic, message) {
    const { topicRequest, topicApproved, topicRejected, topicWhatsappSend } = this.config;
    const data = JSON.parse(message.toString());

    if (topic === topicRequest) {
      await this._handleAvailabilityRequest(data);
      return;
    }

    if (topic === topicApproved) {
      await this._handleProviderApproved(data);
      return;
    }

    if (topic === topicRejected) {
      await this._handleProviderRejected(data);
      return;
    }

    // MQTT MIGRATION Fase 1: Manejar envío de mensajes WhatsApp
    if (topic === topicWhatsappSend) {
      await this._handleWhatsappSend(data);
      return;
    }
  }

  /**
   * Maneja solicitudes de disponibilidad
   * @private
   * @param {object} data - Datos de la solicitud
   */
  async _handleAvailabilityRequest(data) {
    const reqId = data.req_id || 'sin-id';
    const servicio = data.servicio || 'servicio';
    const ciudad = data.ciudad || '';
    const candidatos = Array.isArray(data.candidatos) ? data.candidatos : [];
    const timeoutSeg = Number(data.tiempo_espera_segundos) || 60;
    const textoTiempo = this._formatTime(timeoutSeg);

    for (const cand of candidatos) {
      const phoneRaw = cand.phone || cand.phone_number || cand.contact || cand.contact_phone;
      const phone = this._normalizeWhatsAppNumber(phoneRaw);
      if (!phone) {
        console.warn(`⚠️ Candidato sin número válido: ${JSON.stringify(cand)}`);
        continue;
      }

      const providerName =
        cand.name || cand.provider_name || cand.nombre || cand.display_name || 'Proveedor';
      const ciudadTexto = (ciudad || '').trim();
      const ubicacion = ciudadTexto ? ` en **${ciudadTexto}**` : '';
      const expiresAt = Date.now() + timeoutSeg * 1000;

      this._registerRequest(reqId, phone, expiresAt, cand.id || cand.provider_id || null);

      const servicioEnfatizado = servicio ? `**${servicio}**` : '**servicio**';
      const lineasPregunta = [
        `Hola, ${providerName}.`,
        '',
        `¿Tienes disponibilidad para atender ${servicioEnfatizado}${ubicacion} y coordinar con el cliente?`,
        '',
        `*⏳ Tienes ${textoTiempo} para responder. Luego tu respuesta ya no contará para este requerimiento.*`,
        '',
        `Ref: ${reqId}`,
      ];
      const lineasOpciones = [
        '*Responde con el número de tu opción:*',
        '',
        '1) Sí, disponible',
        '2) No, no disponible',
        '',
        `Ref: ${reqId}`,
      ];

      const textoPregunta = lineasPregunta.join('\n');
      const textoOpciones = lineasOpciones.join('\n');

      console.warn(
        `[PROMPT DISPONIBILIDAD] req=${reqId} destino=${phone} ->\n${textoPregunta}\n--\n${textoOpciones}`
      );

      try {
        await this._sendText(phone, textoPregunta);
        await this._sendText(phone, textoOpciones);
        console.warn(`📨 Ping disponibilidad enviado a ${phone} req=${reqId}`);
      } catch (err) {
        console.error(`❌ No se pudo enviar ping a ${phone}:`, err.message || err);
      }
    }
  }

  /**
   * Maneja aprobación de proveedor
   * @private
   * @param {object} data - Datos de aprobación
   */
  async _handleProviderApproved(data) {
    const providerId = data?.provider_id || data?.id;
    const phone = data?.phone;
    const fullName = data?.full_name || '';

    if (!phone) {
      console.warn('⚠️ Evento de aprobación sin teléfono, se ignora');
      return;
    }

    try {
      const soloDigitos = phone.replace(/[^\d]/g, '');

      // 🔥 VALIDACIÓN DE PAÍS
      if (!this._isLid(phone) && !soloDigitos.startsWith('593')) {
        // 📧 Enviar notificación de solo números nacionales
        const mensajeNotificacion = this._buildCountryRestrictionMessage(fullName);
        await this._sendText(phone, mensajeNotificacion);

        console.warn(`⚠️ Intento de aprobación con número no ecuatoriano ${phone} - notificación enviada (provider_id=${providerId || 'n/a'})`);
        return;
      }

      // ✅ Número ecuatoriano válido - enviar aprobación normal
      const mensajeAprobacion = this._buildApprovalMessage(fullName);
      await this._sendText(phone, mensajeAprobacion);
      console.warn(`✅ Notificación de aprobación enviada a ${phone} (provider_id=${providerId || 'n/a'})`);
    } catch (err) {
      console.error(`❌ Error enviando notificación de aprobación a ${phone}:`, err.message || err);
    }
  }

  /**
   * Maneja rechazo de proveedor
   * @private
   * @param {object} data - Datos de rechazo
   */
  async _handleProviderRejected(data) {
    const providerId = data?.provider_id || data?.id;
    const phone = data?.phone;
    const fullName = data?.full_name || '';
    const notes = data?.notes;

    if (!phone) {
      console.warn('⚠️ Evento de rechazo sin teléfono, se ignora');
      return;
    }

    try {
      const mensaje = this._buildRejectionMessage(fullName, notes);
      await this._sendText(phone, mensaje);
      console.warn(`✅ Notificación de rechazo enviada a ${phone} (provider_id=${providerId || 'n/a'})`);
    } catch (err) {
      console.error(`❌ Error enviando notificación de rechazo a ${phone}:`, err.message || err);
    }
  }

  /**
   * Registra una solicitud de disponibilidad activa
   * @private
   * @param {string} reqId - ID de requerimiento
   * @param {string} phone - Teléfono del proveedor
   * @param {number} expiresAt - Timestamp de expiración
   * @param {string} providerId - ID del proveedor
   */
  _registerRequest(reqId, phone, expiresAt, providerId) {
    const current = this.solicitudesPorReq.get(reqId) || new Set();
    current.add(phone);
    this.solicitudesPorReq.set(reqId, current);

    const timer = setTimeout(async () => {
      const active = this.solicitudesActivas.get(phone);
      if (!active || active.reqId !== reqId) return;

      this.solicitudesActivas.delete(phone);
      current.delete(phone);
      if (current.size === 0) {
        this.solicitudesPorReq.delete(reqId);
      }

      try {
        await this._sendText(
          phone,
          '*El tiempo de respuesta ha caducado y tu respuesta ya no contará para este requerimiento.*'
        );
      } catch (err) {
        console.error(`❌ No se pudo notificar expiración a ${phone}:`, err.message || err);
      }
    }, Math.max(1000, expiresAt - Date.now()));

    this.solicitudesActivas.set(phone, { reqId, providerId, expiresAt, timer });
  }

  /**
   * Procesa una respuesta de disponibilidad de un proveedor
   * @param {string} phone - Teléfono del proveedor
   * @param {string} opcion - Opción seleccionada (1 o 2)
   * @returns {object} Resultado del procesamiento
   */
  processAvailabilityResponse(phone, opcion) {
    const solicitud = this.solicitudesActivas.get(phone);
    if (!solicitud) {
      return { handled: false };
    }

    const isYes = opcion === '1' || opcion === 'si' || opcion === 'sí';
    const ahora = Date.now();
    const reqId = solicitud.reqId;

    // Si la solicitud ya expiró
    if (solicitud.expiresAt && ahora > solicitud.expiresAt) {
      this.solicitudesActivas.delete(phone);
      const setReq = this.solicitudesPorReq.get(reqId);
      if (setReq) {
        setReq.delete(phone);
        if (setReq.size === 0) this.solicitudesPorReq.delete(reqId);
      }
      return { handled: true, expired: true };
    }

    // Control de cupo máximo
    const aceptadasPrevias = this.respuestasPorReq.get(reqId) || 0;
    if (aceptadasPrevias >= this.config.maxResponses) {
      this.solicitudesActivas.delete(phone);
      const setReq = this.solicitudesPorReq.get(reqId);
      if (setReq) {
        setReq.delete(phone);
        if (setReq.size === 0) this.solicitudesPorReq.delete(reqId);
      }
      return { handled: true, full: true };
    }

    const estado = isYes ? 'accepted' : 'declined';
    this._publishResponse(reqId, solicitud.providerId, estado);

    this.solicitudesActivas.delete(phone);
    const setReq = this.solicitudesPorReq.get(reqId);
    if (setReq) {
      setReq.delete(phone);
      if (setReq.size === 0) this.solicitudesPorReq.delete(reqId);
    }

    if (isYes) {
      const nuevoConteo = aceptadasPrevias + 1;
      this.respuestasPorReq.set(reqId, nuevoConteo);
      return { handled: true, accepted: true, count: nuevoConteo };
    }

    return { handled: true, accepted: false };
  }

  /**
   * Publica una respuesta de disponibilidad en MQTT
   * @private
   * @param {string} reqId - ID de requerimiento
   * @param {string} providerId - ID del proveedor
   * @param {string} estado - Estado de la respuesta
   */
  _publishResponse(reqId, providerId, estado) {
    if (!this.client || !this.client.connected) return;

    const { topicResponse } = this.config;
    const payload = JSON.stringify({ req_id: reqId, provider_id: providerId, estado });

    this.client.publish(topicResponse, payload, err => {
      if (err) {
        console.error('❌ No se pudo publicar respuesta MQTT:', err.message || err);
      } else {
        console.warn(`📤 Respuesta disponibilidad publicada req=${reqId} provider=${providerId} estado=${estado}`);
      }
    });
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
   * Verifica si un valor es un LID de WhatsApp
   * @private
   * @param {string} valor - Valor a verificar
   * @returns {boolean} True si es un LID
   */
  _isLid(valor) {
    if (!valor) return false;
    return String(valor).trim().endsWith('@lid');
  }

  /**
   * Formatea un tiempo en segundos a texto legible
   * @private
   * @param {number} segundos - Tiempo en segundos
   * @returns {string} Tiempo formateado
   */
  _formatTime(segundos) {
    const s = Number(segundos) || 0;
    if (s >= 60) {
      const mins = Math.round(s / 60);
      return `${mins} minuto${mins === 1 ? '' : 's'}`;
    }
    return `${s} segundo${s === 1 ? '' : 's'}`;
  }

  /**
   * Construye mensaje de aprobación
   * @private
   * @param {string} nombre - Nombre del proveedor
   * @returns {string} Mensaje formateado
   */
  _buildApprovalMessage(nombre) {
    const nombreCorto = (nombre || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .join(' ');
    const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
    return `${saludo} ✅ tu perfil está aprobado. Bienvenido/a a TinkuBot; permanece pendiente de las próximas solicitudes.`;
  }

  /**
   * Construye mensaje de restricción de país
   * @private
   * @param {string} nombre - Nombre del proveedor
   * @returns {string} Mensaje formateado
   */
  _buildCountryRestrictionMessage(nombre) {
    const nombreCorto = (nombre || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .join(' ');
    const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
    return `${saludo} 🌎 Gracias por tu interés en TinkuBot. Por el momento, el registro de proveedores está disponible solo para números nacionales de Ecuador. Si tienes un número ecuatoriano, por favor regístrate con ese número para continuar.`;
  }

  /**
   * Construye mensaje de rechazo
   * @private
   * @param {string} nombre - Nombre del proveedor
   * @param {string} notas - Notas del rechazo
   * @returns {string} Mensaje formateado
   */
  _buildRejectionMessage(nombre, notas) {
    const nombreCorto = (nombre || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .join(' ');
    const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
    const motivo = notas && String(notas).trim().length > 0 ? ` Motivo: ${notas}` : '';
    return `${saludo} 🚫 tu registro fue revisado y requiere ajustes.${motivo} Puedes actualizar tus datos y volver a enviarlos cuando estés listo.`;
  }

  /**
   * Maneja envío de mensajes WhatsApp vía MQTT (Fase 1)
   * @private
   * @param {object} mqttMessage - Mensaje MQTT según estándar MQTTMessage
   */
  async _handleWhatsappSend(mqttMessage) {
    // Extraer payload del estándar MQTTMessage
    // Formato: { message_id, timestamp, source_service, type, payload: { phone/message, message } }
    const payload = mqttMessage?.payload || mqttMessage; // Fallback por compatibilidad

    const phone = payload?.phone || payload?.to;
    const message = payload?.message;

    if (!phone || !message) {
      console.warn('⚠️ Mensaje MQTT whatsapp/send sin phone/message en payload, se ignora:', mqttMessage);
      return;
    }

    try {
      // Normalizar número y enviar
      const normalizedPhone = this._normalizeWhatsAppNumber(phone);
      await this._sendText(normalizedPhone, message);

      console.warn(`✅ Mensaje WhatsApp enviado vía MQTT a ${phone} (topic=whatsapp/proveedores/send)`);
    } catch (err) {
      console.error(`❌ Error enviando mensaje WhatsApp vía MQTT a ${phone}:`, err.message || err);
    }
  }

  /**
   * Envía un mensaje de texto
   * @private
   * @param {string} numero - Número de destino
   * @param {string} texto - Texto a enviar
   * @returns {Promise} Resultado del envío
   */
  async _sendText(numero, texto) {
    const destino = this._normalizeWhatsAppNumber(numero);
    if (!destino) {
      throw new Error(`Número de WhatsApp inválido: ${numero}`);
    }
    const contenido = texto || ' ';
    return this.whatsappClient.sendMessage(destino, contenido);
  }

  /**
   * Verifica si el cliente está conectado
   * @returns {boolean} True si está conectado
   */
  isConnected() {
    return this.client && this.client.connected;
  }

  /**
   * Obtiene las solicitudes activas para un teléfono
   * @param {string} phone - Teléfono del proveedor
   * @returns {object|null} Solicitud activa o null
   */
  getActiveRequest(phone) {
    return this.solicitudesActivas.get(phone) || null;
  }

  /**
   * Obtiene el conjunto de teléfonos para un requerimiento
   * @param {string} reqId - ID de requerimiento
   * @returns {Set<string>} Conjunto de teléfonos
   */
  getRequestPhones(reqId) {
    return this.solicitudesPorReq.get(reqId) || new Set();
  }
}

module.exports = MqttClient;
