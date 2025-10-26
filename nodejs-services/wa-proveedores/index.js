const express = require('express');
const { Client, RemoteAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const cors = require('cors');
const axios = require('axios');
const http = require('http');
const { Server } = require('socket.io');
const SupabaseStore = require('./SupabaseStore');

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

const app = express();
const port = resolvePort(
  5002,
  process.env.PROVEEDORES_WHATSAPP_PORT,
  process.env.WHATSAPP_PROVEEDORES_PORT
);
const instanceId = process.env.PROVEEDORES_INSTANCE_ID || 'bot-proveedores';
const instanceName = process.env.PROVEEDORES_INSTANCE_NAME || 'TinkuBot Proveedores';

// Configuración de servicios externos
// ESPECIALIZADO: Siempre usa el AI Service Proveedores
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
const AI_SERVICE_URL =
  process.env.PROVEEDORES_AI_SERVICE_URL || fallbackAiHosts[0];

// Configuración de Supabase para almacenamiento de sesiones
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_BACKEND_API_KEY;
const supabaseBucket = process.env.SUPABASE_BUCKET_NAME;

// Validar configuración de Supabase
if (!supabaseUrl || !supabaseKey || !supabaseBucket) {
  console.error('❌ Error: Faltan variables de entorno de Supabase');
  console.error('Requeridas: SUPABASE_URL, SUPABASE_BACKEND_API_KEY, SUPABASE_BUCKET_NAME');
  process.exit(1);
}

// Inicializar Supabase Store
const supabaseStore = new SupabaseStore(supabaseUrl, supabaseKey, supabaseBucket);
console.warn('✅ Supabase Store inicializado');

// Configuración de instancia
console.warn(`🤖 Iniciando ${instanceName} (ID: ${instanceId})`);
console.warn(`📱 Puerto: ${port}`);

// Middleware
app.use(cors());
app.use(express.json());

// Health check simple para monitoreo
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    instanceId,
    aiServiceUrl: AI_SERVICE_URL,
    uptime_seconds: Math.round(process.uptime()),
  });
});

// Configurar servidor HTTP y WebSocket
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST'],
  },
});

let qrCodeData = null;
let clientStatus = 'disconnected';
let isRefreshing = false;
let lastRemoteSessionLog = 0;
const SESSION_LOG_INTERVAL_MS = 5 * 60 * 1000;

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

// Función para procesar mensajes con IA
// ACTUALIZADO: Ahora usa el endpoint /handle-whatsapp-message que incluye gestión de sesiones
async function processWithAI(message) {
  try {
    const rawText = message.body || '';
    const messageText = rawText.trim();
    let mediaAttachment = null;

    if (message.hasMedia) {
      try {
        const media = await message.downloadMedia();
        if (media && media.data) {
          mediaAttachment = {
            type: media.mimetype && media.mimetype.startsWith('image/') ? 'image' : 'file',
            mimetype: media.mimetype,
            filename: media.filename,
            base64: media.data,
          };
        }
      } catch (downloadError) {
        console.error('Error descargando media de WhatsApp:', downloadError);
      }
    }

    if (!messageText && !mediaAttachment) {
      return 'Lo siento, solo puedo procesar mensajes de texto o imágenes claras. Por favor, envía tu consulta nuevamente.';
    }

    const payload = {
      id: message.id._serialized || message.id,
      from_number: message.from,
      content: messageText || null,
      timestamp: new Date(),
      status: 'received',
    };

    if (mediaAttachment) {
      payload.media_base64 = mediaAttachment.base64;
      payload.media_mimetype = mediaAttachment.mimetype;
      payload.media_filename = mediaAttachment.filename;
      payload.attachments = [
        {
          type: mediaAttachment.type,
          mimetype: mediaAttachment.mimetype,
          filename: mediaAttachment.filename,
          base64: mediaAttachment.base64,
        },
      ];
    }

    const response = await axios.post(`${AI_SERVICE_URL}/handle-whatsapp-message`, payload);

    const data = response.data || {};
    const replies = [];

    if (Array.isArray(data.messages)) {
      for (const item of data.messages) {
        if (!item) continue;
        if (typeof item === 'string' && item.trim()) {
          replies.push(item.trim());
          continue;
        }
        if (item.response && typeof item.response === 'string' && item.response.trim()) {
          replies.push(item.response.trim());
        }
      }
    }

    const primaryResponse =
      data.ai_response || data.response || data.message || data.prompt || null;
    if (primaryResponse && typeof primaryResponse === 'string' && primaryResponse.trim()) {
      replies.push(primaryResponse.trim());
    }

    return replies.length > 0 ? replies : ['Procesando tu mensaje...'];
  } catch (error) {
    console.error('Error al procesar con IA:', error);
    if (error.response && error.response.status === 400) {
      return [
        'Lo siento, no pude procesar tu mensaje. Por favor, intenta enviar un mensaje de texto claro.',
      ];
    }
    return ['Lo siento, estoy teniendo problemas para procesar tu mensaje.'];
  }
}

console.warn('Inicializando cliente de WhatsApp con RemoteAuth...');

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

client.on('qr', qr => {
  console.warn(`[${instanceName}] QR Code recibido, generándolo en terminal y guardándolo...`);
  qrcode.generate(qr, { small: true });
  qrCodeData = qr; // Guardamos el QR para la API
  clientStatus = 'qr_ready';

  // Notificar a clientes WebSocket
  io.emit('status', {
    status: 'qr_ready',
    qr,
    timestamp: new Date().toISOString(),
  });
});

client.on('authenticated', () => {
  console.warn(`[${instanceName}] Autenticación exitosa (authenticated)`);
  clientStatus = 'connected';
  qrCodeData = null;
  io.emit('status', { status: 'connected', timestamp: new Date().toISOString() });
});

client.on('auth_failure', msg => {
  console.error(`[${instanceName}] Falla de autenticación:`, msg);
  clientStatus = 'disconnected';
  io.emit('status', {
    status: 'disconnected',
    reason: 'auth_failure',
    timestamp: new Date().toISOString(),
  });
  resetWhatsAppSession('auth_failure', { attemptLogout: false }).catch(error =>
    console.error(`[${instanceName}] Error intentando recuperar tras auth_failure:`, error)
  );
});

client.on('ready', () => {
  console.warn(`[${instanceName}] ¡Cliente de WhatsApp está listo con sesión remota!`);
  qrCodeData = null; // Ya no necesitamos el QR
  clientStatus = 'connected';

  // Notificar a clientes WebSocket
  io.emit('status', {
    status: 'connected',
    timestamp: new Date().toISOString(),
  });
});

client.on('remote_session_saved', () => {
  const now = Date.now();
  if (now - lastRemoteSessionLog < SESSION_LOG_INTERVAL_MS) {
    return;
  }

  lastRemoteSessionLog = now;
  console.debug(`[${instanceName}] Sesión guardada en Supabase Storage`);
});

// Manejar mensajes entrantes
client.on('message', async message => {
  console.warn(
    `[${instanceName}] Mensaje recibido de ${message.from}:`,
    message.body || '[Mensaje sin texto]'
  );

  // Ignorar mensajes de broadcast y del sistema
  if (
    message.from === 'status@broadcast' ||
    message.from.endsWith('@g.us') ||
    message.from.endsWith('@broadcast')
  ) {
    return;
  }

  // ACTUALIZADO: La gestión de sesiones está integrada en processWithAI()
  // Ya no es necesario llamar a saveSession() por separado

  // Procesar con IA y responder (ahora incluye gestión automática de sesiones)
  try {
    const chat = await message.getChat();
    const responses = await processWithAI(message);
    const replies = Array.isArray(responses) ? responses : [responses];

    for (const replyText of replies) {
      if (!replyText || typeof replyText !== 'string') continue;
      await chat.sendMessage(replyText);
      console.warn('Respuesta enviada:', replyText);
    }
  } catch (error) {
    console.error('Error al procesar mensaje:', error);
    const chat = await message.getChat();
    // Enviar respuesta de fallback solo si falla la IA
    await chat.sendMessage(
      'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.'
    );
  }
});

client.on('disconnected', reason => {
  const timestamp = new Date().toISOString();
  console.error(`[${instanceName}] CLIENTE DESCONECTADO - Razón: ${reason || 'sin motivo'}`);
  console.error(`[${instanceName}] Timestamp desconexión: ${timestamp}`);
  console.error(`[${instanceName}] Estado previo a reinicio: ${clientStatus}`);
  clientStatus = 'disconnected';

  io.emit('status', {
    status: 'disconnected',
    reason,
    timestamp,
  });

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
        error: 'Ya se está procesando una regeneración para esta instancia.',
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

// Endpoint de Health Check extendido
app.get('/health', async (req, res) => {
  const healthStatus = {
    status: 'healthy',
    instance: instanceId,
    name: instanceName,
    port,
    whatsapp_status: clientStatus,
    ai_service: 'unknown',
    websocket_connected: true,
    timestamp: new Date().toISOString(),
  };

  // Verificar conexión con AI Service Proveedores
  try {
    const aiResponse = await axios.get(`${AI_SERVICE_URL}/health`, {
      timeout: 5000,
    });
    healthStatus.ai_service = 'connected';
    healthStatus.ai_service_status = aiResponse.data.status || 'ok';
  } catch (error) {
    healthStatus.ai_service = 'disconnected';
    healthStatus.ai_service_error = error.message;
  }

  // Si WhatsApp no está conectado, marcar como degradado
  if (clientStatus !== 'connected') {
    healthStatus.status = 'degraded';
  }

  // Si AI Service no está conectado, marcar como unhealthy
  if (healthStatus.ai_service === 'disconnected') {
    healthStatus.status = 'unhealthy';
  }

  res.json(healthStatus);
});

server.listen(port, () => {
  console.warn(`🚀 ${instanceName} (ID: ${instanceId}) escuchando en http://localhost:${port}`);
  console.warn('🔌 WebSocket habilitado para notificaciones en tiempo real');
});
