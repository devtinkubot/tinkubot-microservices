/**
 * envConfig.js
 * Configuración centralizada de variables de entorno y parámetros del servicio
 *
 * Responsabilidad:
 * - Validar y resolver variables de entorno
 * - Proporcionar configuración tipada y validada
 * - Centralizar toda la lógica de configuración
 */

const parsePort = value => {
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? num : undefined;
};

const resolvePort = (defaultValue, ...candidates) => {
  for (const candidate of candidates) {
    const parsed = parsePort(candidate);
    if (parsed !== undefined) {
      return parsed;
    }
  }
  return defaultValue;
};

/**
 * Clase de configuración centralizada
 * Valida y proporciona acceso a todas las variables de entorno del servicio
 */
class EnvConfig {
  constructor() {
    // Configuración de puerto e instancia
    this.port = resolvePort(
      5001,
      process.env.CLIENTES_WHATSAPP_PORT,
      process.env.WHATSAPP_CLIENTES_PORT
    );
    this.instanceId = process.env.CLIENTES_INSTANCE_ID || 'bot-clientes';
    this.instanceName = process.env.CLIENTES_INSTANCE_NAME || 'TinkuBot Clientes';
    this.requestTimeoutMs = parseInt(process.env.REQUEST_TIMEOUT_MS || '8000', 10);
    this.logSamplingRate = parseInt(process.env.LOG_SAMPLING_RATE || '10', 10);

    // Configuración de AI Service
    this.aiServiceUrl = this._resolveAIServiceUrl();

    // Configuración de Supabase
    this.supabase = {
      url: process.env.SUPABASE_URL,
      key: process.env.SUPABASE_SERVICE_KEY,
      bucket: process.env.SUPABASE_BUCKET_NAME
    };

    // Configuración de middleware
    this.rateLimitMax = parseInt(process.env.RATE_LIMIT_MAX || '120', 10);
    this.bodySizeLimit = process.env.BODY_SIZE_LIMIT || '200kb';

    // Configuración de HTTP agents
    this.httpAgent = {
      keepAlive: true,
      maxSockets: 20
    };

    this.axiosTimeout = 5000;

    // Configuración de MQTT (NUEVO - MQTT Migration Fase 1)
    this.mqtt = {
      host: process.env.MQTT_HOST || 'mosquitto',
      port: parseInt(process.env.MQTT_PORT || '1883', 10),
      username: process.env.MQTT_USUARIO,
      password: process.env.MQTT_PASSWORD,
      // MQTT MIGRATION Fase 1: Topic para enviar mensajes WhatsApp
      topicWhatsappSend: process.env.MQTT_TEMA_WHATSAPP_SEND || 'whatsapp/clientes/send',
    };
  }

  /**
   * Resuelve la URL del AI Service con fallbacks
   * @private
   */
  _resolveAIServiceUrl() {
    // AI Clientes ahora usa el health server en puerto 8888
    // que maneja tanto /health como /handle-whatsapp-message
    const defaultAiPort = resolvePort(
      8888,
      process.env.HEALTH_SERVER_PORT,
      process.env.CLIENTES_SERVER_PORT,
      process.env.AI_SERVICE_CLIENTES_PORT
    );

    const fallbackAiHosts = [
      process.env.SERVER_DOMAIN && `http://${process.env.SERVER_DOMAIN}:${defaultAiPort}`,
      `http://ai-clientes:${defaultAiPort}`,
      'http://ai-srv-clientes:8888',
    ].filter(Boolean);

    const aiServiceUrl =
      process.env.AI_SERVICE_CLIENTES_URL ||
      process.env.CLIENTES_AI_SERVICE_URL ||
      fallbackAiHosts[0];

    console.warn(`[${this.instanceName}] IA Clientes URL: ${aiServiceUrl}`);
    return aiServiceUrl;
  }

  /**
   * Valida que toda la configuración requerida esté presente
   * @throws {Error} Si falta configuración crítica
   */
  validate() {
    if (!this.supabase.url || !this.supabase.key || !this.supabase.bucket) {
      console.error('❌ Error: Faltan variables de entorno de Supabase');
      console.error('Requeridas: SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET_NAME');
      throw new Error('Missing required Supabase configuration');
    }
  }

  /**
   * Información de configuración para logging
   */
  getStartupInfo() {
    return {
      instanceName: this.instanceName,
      instanceId: this.instanceId,
      port: this.port,
      mqtt: `host=${this.mqtt.host}:${this.mqtt.port} topic=${this.mqtt.topicWhatsappSend}`
    };
  }
}

// Exportar instancia singleton
const config = new EnvConfig();

// Exportar también las funciones de utilidad para compatibilidad
module.exports = config;
module.exports.parsePort = parsePort;
module.exports.resolvePort = resolvePort;
