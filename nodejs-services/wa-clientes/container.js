/**
 * container.js
 * Contenedor de Inyección de Dependencias
 *
 * Responsabilidad:
 * - Registrar y resolver todas las dependencias del servicio
 * - Aplicar Dependency Inversion Principle (DIP)
 * - Centralizar la creación de objetos
 */

const { Client, RemoteAuth } = require('whatsapp-web.js');
const SupabaseStore = require('./SupabaseStore');
const config = require('./src/infrastructure/config/envConfig');
const MessageSenderWithRetry = require('./src/infrastructure/messaging/MessageSenderWithRetry');
const SocketIOServer = require('./src/infrastructure/websocket/SocketIOServer');
const AIServiceClient = require('./src/application/services/AIServiceClient');
const TextMessageHandler = require('./src/application/handlers/TextMessageHandler');
const HandlerRegistry = require('./src/application/handlers/HandlerRegistry');
const createApp = require('./src/presentation/http/app.js');

class ServiceContainer {
  constructor() {
    this._config = null;
    this._supabaseStore = null;
    this._aiServiceClient = null;
    this._whatsappClient = null;
    this._messageSender = null;
    this._handlerRegistry = null;
    this._app = null;
    this._httpServer = null;
    this._socketServer = null;
  }

  /**
   * Inicializa todas las dependencias
   */
  initialize() {
    // Validar configuración
    this._config = config;
    this._config.validate();

    // Inicializar Supabase Store
    const { url: supabaseUrl, key: supabaseKey, bucket: supabaseBucket } = this._config.supabase;
    this._supabaseStore = new SupabaseStore(supabaseUrl, supabaseKey, supabaseBucket);

    // Inicializar AI Service Client
    this._aiServiceClient = new AIServiceClient(this._config.aiServiceUrl);

    // WhatsApp client se inicializa en index.js porque necesita eventos personalizados
    this._whatsappClient = null;

    this._messageSender = null;
    this._handlerRegistry = null;
    this._app = null;
    this._httpServer = null;
    this._socketServer = null;
  }

  /**
   * Registra el cliente de WhatsApp
   * @param {Client} client - Cliente de WhatsApp
   */
  registerWhatsAppClient(client) {
    this._whatsappClient = client;
    this._messageSender = new MessageSenderWithRetry(client);

    // Inicializar HandlerRegistry y registrar handlers
    this._handlerRegistry = new HandlerRegistry();
    this._handlerRegistry.register(new TextMessageHandler(this._messageSender, this._aiServiceClient));
  }

  /**
   * Obtiene la configuración
   */
  get config() {
    return this._config;
  }

  /**
   * Obtiene el Supabase Store
   */
  get supabaseStore() {
    return this._supabaseStore;
  }

  /**
   * Obtiene el AI Service Client
   */
  get aiServiceClient() {
    return this._aiServiceClient;
  }

  /**
   * Obtiene el cliente de WhatsApp
   */
  get whatsappClient() {
    return this._whatsappClient;
  }

  /**
   * Obtiene el MessageSender
   */
  get messageSender() {
    return this._messageSender;
  }

  /**
   * Obtiene el HandlerRegistry
   */
  get handlerRegistry() {
    return this._handlerRegistry;
  }

  /**
   * Crea la aplicación Express con todas las rutas
   * @param {object} runtimeServices - Servicios en tiempo de ejecución (clientStatus, qrCodeData, etc.)
   */
  createExpressApp(runtimeServices) {
    const services = {
      config: this._config,
      instanceId: this._config.instanceId,
      instanceName: this._config.instanceName,
      port: this._config.port,
      clientStatus: runtimeServices.clientStatus,
      aiServiceClient: this._aiServiceClient,
      qrCodeData: runtimeServices.qrCodeData,
      resetWhatsAppSession: runtimeServices.resetWhatsAppSession,
      messageSender: this._messageSender
    };

    this._app = createApp(services);
    return this._app;
  }

  /**
   * Crea el servidor HTTP
   */
  createHttpServer() {
    const http = require('http');
    this._httpServer = http.createServer(this._app);
    return this._httpServer;
  }

  /**
   * Crea el servidor WebSocket
   */
  createSocketServer() {
    this._socketServer = new SocketIOServer(this._httpServer);
    return this._socketServer;
  }

  /**
   * Obtiene el servidor HTTP
   */
  get httpServer() {
    return this._httpServer;
  }

  /**
   * Obtiene el servidor WebSocket
   */
  get socketServer() {
    return this._socketServer;
  }
}

module.exports = new ServiceContainer();
