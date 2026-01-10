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
      5002,
      process.env.PROVEEDORES_WHATSAPP_PORT,
      process.env.WHATSAPP_PROVEEDORES_PORT
    );
    this.instanceId = process.env.PROVEEDORES_INSTANCE_ID || 'bot-proveedores';
    this.instanceName = process.env.PROVEEDORES_INSTANCE_NAME || 'TinkuBot Proveedores';
    this.requestTimeoutMs = parseInt(process.env.REQUEST_TIMEOUT_MS || '8000', 10);
    this.logSamplingRate = parseInt(process.env.LOG_SAMPLING_RATE || '10', 10);

    // Configuración de AI Service (ESPECIALIZADO para Proveedores)
    this.aiServiceUrl = this._resolveAIServiceUrl();

    // Configuración de Supabase
    this.supabase = {
      url: process.env.SUPABASE_URL,
      key: process.env.SUPABASE_BACKEND_API_KEY,
      bucket: process.env.SUPABASE_BUCKET_NAME,
      providersTable: process.env.SUPABASE_PROVIDERS_TABLE || 'providers'
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

    // Configuración de MQTT (NUEVO - específico de PROVEEDORES)
    this.mqtt = {
      host: process.env.MQTT_HOST || 'mosquitto',
      port: parseInt(process.env.MQTT_PORT || '1883', 10),
      username: process.env.MQTT_USUARIO,
      password: process.env.MQTT_PASSWORD,
      topicRequest: process.env.MQTT_TEMA_SOLICITUD || 'av-proveedores/solicitud',
      topicResponse: process.env.MQTT_TEMA_RESPUESTA || 'av-proveedores/respuesta',
      topicApproved: process.env.MQTT_TEMA_PROVEEDOR_APROBADO || 'providers/approved',
      topicRejected: process.env.MQTT_TEMA_PROVEEDOR_RECHAZADO || 'providers/rejected',
      maxResponses: 5
    };
  }

  /**
   * Resuelve la URL del AI Service con fallbacks
   * ESPECIALIZADO: Siempre usa el AI Service Proveedores
   * @private
   */
  _resolveAIServiceUrl() {
    const defaultAiPort = resolvePort(
      8002,
      process.env.PROVEEDORES_SERVER_PORT,
      process.env.AI_SERVICE_PROVEEDORES_PORT
    );

    const fallbackAiHosts = [
      process.env.SERVER_DOMAIN && `http://${process.env.SERVER_DOMAIN}:${defaultAiPort}`,
      `http://ai-proveedores:${defaultAiPort}`,
      'http://ai-srv-proveedores:8002',
    ].filter(Boolean);

    const aiServiceUrl =
      process.env.PROVEEDORES_AI_SERVICE_URL ||
      fallbackAiHosts[0];

    console.warn(`[${this.instanceName}] IA Proveedores URL: ${aiServiceUrl}`);
    return aiServiceUrl;
  }

  /**
   * Valida que toda la configuración requerida esté presente
   * @throws {Error} Si falta configuración crítica
   */
  validate() {
    if (!this.supabase.url || !this.supabase.key || !this.supabase.bucket) {
      console.error('❌ Error: Faltan variables de entorno de Supabase');
      console.error('Requeridas: SUPABASE_URL, SUPABASE_BACKEND_API_KEY, SUPABASE_BUCKET_NAME');
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
      mqtt: `host=${this.mqtt.host}:${this.mqtt.port} topic_request=${this.mqtt.topicRequest}`
    };
  }
}

// Exportar instancia singleton
const config = new EnvConfig();

// Exportar también las funciones de utilidad para compatibilidad
module.exports = config;
module.exports.parsePort = parsePort;
module.exports.resolvePort = resolvePort;
