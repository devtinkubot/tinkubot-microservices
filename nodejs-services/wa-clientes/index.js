const express = require('express');
const { Client, MessageMedia, RemoteAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const axios = require('axios');
const http = require('http');
const https = require('https');
const SupabaseStore = require('./SupabaseStore');
const config = require('./src/infrastructure/config/envConfig');
const axiosClient = require('./src/infrastructure/http/axiosClient');
const MessageSenderWithRetry = require('./src/infrastructure/messaging/MessageSenderWithRetry');
const SocketIOServer = require('./src/infrastructure/websocket/SocketIOServer');
const AIServiceClient = require('./src/application/services/AIServiceClient');
const TextMessageHandler = require('./src/application/handlers/TextMessageHandler');
const HandlerRegistry = require('./src/application/handlers/HandlerRegistry');
const healthRoutes = require('./src/presentation/http/routes/health.routes');

// Validar configuración
config.validate();

const app = express();
const port = config.port;
const instanceId = config.instanceId;
const instanceName = config.instanceName;
const REQUEST_TIMEOUT_MS = config.requestTimeoutMs;
const AI_SERVICE_URL = config.aiServiceUrl;

// Inicializar AI Service Client
const aiServiceClient = new AIServiceClient(AI_SERVICE_URL);

// Configuración de Supabase para almacenamiento de sesiones
const { url: supabaseUrl, key: supabaseKey, bucket: supabaseBucket } = config.supabase;

// Inicializar Supabase Store
const supabaseStore = new SupabaseStore(supabaseUrl, supabaseKey, supabaseBucket);
console.warn('✅ Supabase Store inicializado');

// Configuración de instancia
const startupInfo = config.getStartupInfo();
console.warn(`🤖 Iniciando ${startupInfo.instanceName} (ID: ${startupInfo.instanceId})`);
console.warn(`📱 Puerto: ${startupInfo.port}`);

// Middleware
app.use(cors());
app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(compression());
app.use(
  rateLimit({
    windowMs: 60 * 1000,
    max: config.rateLimitMax,
    standardHeaders: true,
    legacyHeaders: false
  })
);
app.use(
  express.json({
    limit: config.bodySizeLimit
  })
);
app.use((req, res, next) => {
  res.setTimeout(REQUEST_TIMEOUT_MS, () => {
    if (!res.headersSent) {
      res.status(503).json({ error: 'Request timed out' });
    }
  });
  next();
});

// Endpoint simple para envíos salientes desde otros servicios
app.post('/send', async (req, res) => {
  try {
    const { to, message } = req.body || {};
    if (!to || !message) {
      return res.status(400).json({ error: 'to and message are required' });
    }
    if (typeof to !== 'string' || typeof message !== 'string') {
      return res.status(400).json({ error: 'invalid parameters' });
    }
    if (message.length > 1000) {
      return res.status(413).json({ error: 'message too long' });
    }
    await messageSender.sendText(to, message);
    return res.json({ status: 'sent' });
  } catch (err) {
    console.error('Error en /send:', err.message || err);
    return res.status(500).json({ error: 'failed to send message' });
  }
});

// Configurar servidor HTTP y WebSocket
const server = http.createServer(app);
const socketServer = new SocketIOServer(server);

let qrCodeData = null;
let clientStatus = 'disconnected';
let isRefreshing = false;
let messageSender; // Se inicializará después de crear el cliente

console.warn('Inicializando cliente de WhatsApp con RemoteAuth...');

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

function shouldAutoReconnect(reason) {
  if (!reason) return true;
  const normalized = String(reason).toLowerCase();
  if (normalized.includes('logout')) {
    return false;
  }
  if (normalized.includes('multidevice')) {
    return true;
  }
  return true;
}

async function resetWhatsAppSession(trigger = 'manual', { attemptLogout = true } = {}) {
  if (isRefreshing) {
    console.warn(
      `[${instanceName}] Reinicio (${trigger}) ignorado: ya existe un proceso de regeneración en curso.`
    );
    return 'in_progress';
  }

  isRefreshing = true;
  console.warn(`[${instanceName}] Iniciando reinicio de sesión (${trigger})...`);

  try {
    if (attemptLogout) {
      try {
        await client.logout();
        console.warn(`[${instanceName}] Sesión cerrada correctamente (${trigger}).`);
      } catch (logoutError) {
        console.warn(
          `[${instanceName}] No se pudo cerrar sesión (${trigger}):`,
          logoutError?.message || logoutError
        );
      }
    }

    try {
      await client.destroy();
      console.warn(`[${instanceName}] Cliente destruido (${trigger}); preparando reinicio.`);
    } catch (destroyError) {
      console.warn(
        `[${instanceName}] No se pudo destruir el cliente (${trigger}):`,
        destroyError?.message || destroyError
      );
    }

    try {
      await supabaseStore.delete({ session: instanceId });
      console.warn(`[${instanceName}] Sesión remota eliminada en Supabase (${trigger}).`);
    } catch (storeError) {
      console.warn(
        `[${instanceName}] No se pudo eliminar la sesión remota (${trigger}):`,
        storeError?.message || storeError
      );
    }

    qrCodeData = null;
    clientStatus = 'disconnected';

    await wait(750);

    client
      .initialize()
      .then(() =>
        console.warn(
          `[${instanceName}] Reinicio solicitado (${trigger}) en ejecución. Esperando nuevo QR/estado de conexión.`
        )
      )
      .catch(error =>
        console.error(`[${instanceName}] Error al reinicializar cliente (${trigger}):`, error)
      );
    return 'ok';
  } catch (error) {
    console.error(`[${instanceName}] Error durante el reinicio (${trigger}):`, error);
    throw error;
  } finally {
    isRefreshing = false;
  }
}

const client = new Client({
  authStrategy: new RemoteAuth({
    clientId: instanceId, // Identificador único por instancia
    store: supabaseStore, // Store de Supabase para sesiones remotas
    dataPath: '/app/.wwebjs_auth', // Ruta temporal para sesiones
    backupSyncIntervalMs: 300000, // 5 minutos entre backups
    rmMaxRetries: 4, // Máximo de reintentos para eliminar archivos
  }), // Guardar sesión en Supabase Storage
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--disable-gpu',
      '--disable-extensions',
      '--disable-background-timer-throttling',
      '--disable-backgrounding-occluded-windows',
      '--disable-renderer-backgrounding',
      '--disable-features=TranslateUI',
      '--disable-ipc-flooding-protection',
      '--enable-unsafe-swiftshader',
      '--max-old-space-size=256',
    ],
  },
});

// Inicializar MessageSender con el cliente
messageSender = new MessageSenderWithRetry(client);

// Inicializar HandlerRegistry y registrar handlers
const handlerRegistry = new HandlerRegistry();
handlerRegistry.register(new TextMessageHandler(messageSender, aiServiceClient));
console.warn(`✅ HandlerRegistry inicializado con ${handlerRegistry.count} handler(s)`);

client.on('qr', qr => {
  console.warn(`[${instanceName}] QR Code recibido, generándolo en terminal y guardándolo...`);
  qrcode.generate(qr, { small: true });
  qrCodeData = qr; // Guardamos el QR para la API
  clientStatus = 'qr_ready';

  // Notificar a clientes WebSocket
  socketServer.notifyQR(qr);
});

// Marcar como conectado al autenticarse (al escanear QR)
client.on('authenticated', () => {
  if (clientStatus !== 'connected') {
    console.warn(`[${instanceName}] Autenticación exitosa (authenticated)`);
  }
  clientStatus = 'connected';
  qrCodeData = null;
  socketServer.notifyConnected();
});

client.on('auth_failure', msg => {
  console.error(`[${instanceName}] Falla de autenticación:`, msg);
  clientStatus = 'disconnected';
  socketServer.notifyAuthFailure(msg);
  resetWhatsAppSession('auth_failure', { attemptLogout: false }).catch(error =>
    console.error(`[${instanceName}] Error intentando recuperar tras auth_failure:`, error)
  );
});

client.on('ready', () => {
  if (clientStatus !== 'connected') {
    console.warn(`[${instanceName}] ¡Cliente de WhatsApp está listo con sesión remota!`);
  }
  qrCodeData = null; // Ya no necesitamos el QR
  clientStatus = 'connected';

  // Notificar a clientes WebSocket
  socketServer.notifyConnected();
});

let lastSessionSavedLog = 0;
const SESSION_LOG_INTERVAL_MS = 5 * 60 * 1000;
client.on('remote_session_saved', () => {
  const now = Date.now();
  if (now - lastSessionSavedLog < SESSION_LOG_INTERVAL_MS) {
    return;
  }

  lastSessionSavedLog = now;
  console.debug(`[${instanceName}] Sesión guardada en Supabase Storage`);
});

// Manejar mensajes entrantes usando HandlerRegistry
client.on('message', async message => {
  await handlerRegistry.dispatch(message);
});

client.on('disconnected', reason => {
  const timestamp = new Date().toISOString();
  console.error(`[${instanceName}] CLIENTE DESCONECTADO - Razón: ${reason || 'sin motivo'}`);
  console.error(`[${instanceName}] Timestamp desconexión: ${timestamp}`);
  console.error(`[${instanceName}] Estado previo a reinicio: ${clientStatus}`);
  clientStatus = 'disconnected';

  socketServer.notifyDisconnected(reason);

  if (!shouldAutoReconnect(reason)) {
    console.warn(`[${instanceName}] Desconexión provocada por logout manual; no se reintenta.`);
    return;
  }

  resetWhatsAppSession('auto-disconnected', { attemptLogout: false }).catch(error =>
    console.error(`[${instanceName}] Error durante reinicio automático tras desconexión:`, error)
  );
});

client.initialize();

// --- Endpoints de la API ---

// Endpoint para obtener el QR code
app.get('/qr', (req, res) => {
  if (clientStatus === 'qr_ready' && qrCodeData) {
    res.json({ qr: qrCodeData });
  } else {
    res.status(404).json({ error: 'QR code no disponible o ya conectado.' });
  }
});

// Endpoint para obtener el estado
app.get('/status', (req, res) => {
  res.json({ status: clientStatus });
});

app.post('/refresh', async (req, res) => {
  try {
    const result = await resetWhatsAppSession('manual', { attemptLogout: true });
    if (result === 'in_progress') {
      return res.status(409).json({
        success: false,
        error: 'Ya hay un proceso de regeneración en curso.',
      });
    }

    res.json({
      success: true,
      message: 'Regeneración de QR iniciada. Escanea el nuevo código cuando aparezca.',
    });
  } catch (error) {
    console.error(`[${instanceName}] Error durante la regeneración manual:`, error);
    res.status(500).json({
      success: false,
      error: 'No se pudo regenerar el código QR.',
    });
  }
});

// Registrar rutas
const services = {
  config,
  instanceId,
  instanceName,
  port,
  clientStatus,
  aiServiceClient
};
healthRoutes(app, services);

server.listen(port, () => {
  console.warn(`🚀 ${instanceName} (ID: ${instanceId}) escuchando en http://localhost:${port}`);
  console.warn('🔌 WebSocket habilitado para notificaciones en tiempo real');
});
