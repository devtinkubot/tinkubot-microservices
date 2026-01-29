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
  5001,
  process.env.CLIENTES_WHATSAPP_PORT,
  process.env.WHATSAPP_CLIENTES_PORT
);
const instanceId = process.env.CLIENTES_INSTANCE_ID || 'bot-clientes';
const instanceName = process.env.CLIENTES_INSTANCE_NAME || 'TinkuBot Clientes';
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS || '8000', 10);
const LOG_SAMPLING_RATE = parseInt(process.env.LOG_SAMPLING_RATE || '10', 10);

// Configuración de servicios externos
// ESPECIALIZADO: Siempre usa el AI Service Clientes
const defaultAiPort = resolvePort(
  8001,
  process.env.CLIENTES_SERVER_PORT,
  process.env.AI_SERVICE_CLIENTES_PORT
);
const fallbackAiHosts = [
  process.env.SERVER_DOMAIN && `http://${process.env.SERVER_DOMAIN}:${defaultAiPort}`,
  `http://ai-clientes:${defaultAiPort}`,
  'http://ai-srv-clientes:8001',
].filter(Boolean);

const AI_SERVICE_URL =
  process.env.AI_SERVICE_CLIENTES_URL ||
  process.env.CLIENTES_AI_SERVICE_URL ||
  fallbackAiHosts[0];
console.warn(`[${instanceName}] IA Clientes URL: ${AI_SERVICE_URL}`);
const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 20 });
const httpsAgent = new https.Agent({ keepAlive: true, maxSockets: 20 });
const axiosClient = axios.create({
  httpAgent,
  httpsAgent,
  timeout: 5000
});

// Configuración de Supabase para almacenamiento de sesiones
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
const supabaseBucket = process.env.SUPABASE_BUCKET_NAME;

// Validar configuración de Supabase
if (!supabaseUrl || !supabaseKey || !supabaseBucket) {
  console.error('❌ Error: Faltan variables de entorno de Supabase');
  console.error('Requeridas: SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET_NAME');
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
app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(compression());
app.use(
  rateLimit({
    windowMs: 60 * 1000,
    max: parseInt(process.env.RATE_LIMIT_MAX || '120', 10),
    standardHeaders: true,
    legacyHeaders: false
  })
);
app.use(
  express.json({
    limit: process.env.BODY_SIZE_LIMIT || '200kb'
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

// Endpoint básico de health check para orquestadores
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    instanceId,
    aiServiceUrl: AI_SERVICE_URL,
    uptime_seconds: Math.round(process.uptime()),
  });
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
    await sendText(to, message);
    return res.json({ status: 'sent' });
  } catch (err) {
    console.error('Error en /send:', err.message || err);
    return res.status(500).json({ error: 'failed to send message' });
  }
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

// Variables para auto-detección de sesión corrupta
let sessionTimeout = null;
let sessionRetryCount = 0;
const MAX_SESSION_RETRIES = 2;

// Variables para tracking de sesión RemoteAuth
let remoteSessionSaved = false;
const MANUAL_SAVE_DELAY_MS = 90000; // 90 segundos

// Envío robusto con retry/backoff para mitigar errores de Puppeteer/Chromium
async function sendWithRetry(sendFn, maxRetries = 3, baseDelayMs = 300) {
  let attempt = 0;
  let lastErr;
  while (attempt <= maxRetries) {
    try {
      return await sendFn();
    } catch (err) {
      lastErr = err;
      const msg = (err && (err.message || err.originalMessage)) || '';
      const retriable =
        /Execution context was destroyed|Target closed|Evaluation failed|Protocol error/i.test(msg);
      if (!retriable || attempt === maxRetries) {
        console.error('sendWithRetry: fallo definitivo:', msg);
        throw err;
      }
      const delay = baseDelayMs * Math.pow(2, attempt);
      console.warn(
        `sendWithRetry: reintentando en ${delay}ms (intento ${attempt + 1}/${maxRetries})`
      );
      await new Promise(r => setTimeout(r, delay));
      attempt++;
    }
  }
  throw lastErr;
}

async function sendText(to, text) {
  const safeText = text || ' ';
  return sendWithRetry(() => client.sendMessage(to, safeText));
}

// Helpers para renderizar UI en WhatsApp (opciones numeradas)
async function sendButtons(to, text) {
  await sendText(to, text || 'Responde con el número de tu opción:');
}

async function sendProviderResults(to, text) {
  // No añadir menú numérico aquí; ai-clientes ya envía la instrucción adecuada.
  await sendText(to, text || ''); // texto ya viene con la instrucción a-e
}

async function sendMedia(to, mediaUrl, caption) {
  if (!mediaUrl) return;
  const media = await MessageMedia.fromUrl(mediaUrl, { unsafeMime: true });
  const options = caption ? { caption } : {};
  return sendWithRetry(() => client.sendMessage(to, media, options));
}

// Helpers HTTP con reintentos
async function postWithRetry(url, payload, { timeout = 15000, retries = 2, baseDelay = 300 } = {}) {
  let attempt = 0;
  let lastErr;
  while (attempt <= retries) {
    try {
      return await axiosClient.post(url, payload, { timeout });
    } catch (err) {
      lastErr = err;
      const msg = err?.message || '';
      const retriable = /ENOTFOUND|ECONNRESET|ETIMEDOUT|EAI_AGAIN|timeout/i.test(msg);
      if (!retriable || attempt === retries) throw err;
      const delay = baseDelay * Math.pow(2, attempt);
      console.warn(`HTTP retry ${attempt + 1}/${retries} en ${delay}ms: ${msg}`);
      await new Promise(r => setTimeout(r, delay));
      attempt++;
    }
  }
  throw lastErr;
}

// Función para procesar mensajes con IA (envía contexto enriquecido)
async function processWithAI(message) {
  try {
    const payload = {
      id: message.id._serialized || message.id,
      from_number: message.from,
      content: message.body || '',
      timestamp: message.timestamp || new Date(),
      status: 'received',
      message_type: message.type,
      message_id: message.id._serialized || message.id || '',
      device_type: message.deviceType || ''
    };

    // Selección por reply-to: si responde citando una opción, usar el texto citado como selected_option
    if (message.hasQuotedMsg) {
      try {
        const quoted = await message.getQuotedMessage();
        if (quoted && quoted.body) {
          payload.selected_option = quoted.body.trim();
        }
      } catch (e) {
        console.warn('No se pudo obtener quoted message:', e.message || e);
      }
    }

    // Ubicación compartida - Manejo mejorado según documentación oficial de WhatsApp Web.js
    if ((message.type === 'location' || message.type === 'live_location') && message.location) {
      console.warn('📍 Objeto location completo:', JSON.stringify(message.location, null, 2));

      // Según documentación oficial, Location tiene propiedades: latitude, longitude, name, address, url
      const lat = message.location.latitude;
      const lng = message.location.longitude;

      console.warn('📍 Coordenadas extraídas - lat:', lat, 'lng:', lng);

      if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
        payload.location = {
          lat: parseFloat(lat),
          lng: parseFloat(lng),
          name: message.location.name || undefined,
          address: message.location.address || undefined,
        };
        console.warn('✅ Ubicación válida procesada:', payload.location);
      } else {
        console.warn('❌ Coordenadas inválidas - lat:', lat, 'lng:', lng);
      }
    }
    // Solo adjuntar ubicación cuando sea mensaje de ubicación nativo
    if (payload.location) {
      console.warn('✅ Ubicación detectada desde objeto location nativo');
    }

    const response = await postWithRetry(`${AI_SERVICE_URL}/handle-whatsapp-message`, payload, {
      timeout: 20000, // acortar para no bloquear el loop
      retries: 0, // evitar duplicar solicitudes en casos de espera larga
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error('Error IA status:', error.response.status, error.response.data);
    } else {
      console.error('Error al procesar con IA:', error.message || error);
    }
    if (error.response && error.response.status === 400) {
      return {
        text: 'Lo siento, no pude procesar tu mensaje. Por favor, intenta enviar un mensaje de texto claro.',
      };
    }
    return { text: 'Lo siento, estoy teniendo problemas para procesar tu mensaje.' };
  }
}

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

async function resetWhatsAppSession(trigger = 'manual', options = {}) {
  if (isRefreshing) {
    console.warn(
      `[${instanceName}] Reinicio (${trigger}) ignorado: ya existe un proceso de regeneración en curso.`
    );
    return 'in_progress';
  }

  isRefreshing = true;
  const { attemptLogout = true, forceDeleteSession = false } = options;
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

    // Si se fuerza la eliminación de la sesión, eliminar de Supabase inmediatamente
    if (forceDeleteSession) {
      try {
        await supabaseStore.delete({ session: instanceId });
        console.warn(`[${instanceName}] ✅ Sesión forzada eliminada de Supabase Storage`);
      } catch (error) {
        console.error(`[${instanceName}] ❌ Error eliminando sesión de Supabase:`, error.message);
      }
    } else {
      try {
        await supabaseStore.delete({ session: instanceId });
        console.warn(`[${instanceName}] Sesión remota eliminada en Supabase (${trigger}).`);
      } catch (storeError) {
        console.warn(
          `[${instanceName}] No se pudo eliminar la sesión remota (${trigger}):`,
          storeError?.message || storeError
        );
      }
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

/**
 * Guarda la sesión manualmente cuando RemoteAuth falla en hacerlo
 */
async function guardarSesionManualmente() {
  const sessionName = `RemoteAuth-${instanceId}`;
  const sessionDir = `/app/.wwebjs_auth/${sessionName}`;

  try {
    const fs = require('fs-extra');
    const pathExists = await fs.pathExists(sessionDir);

    if (!pathExists) {
      console.warn(`[${instanceName}] ⚠️ Directorio de sesión no encontrado: ${sessionDir}`);
      return false;
    }

    const sessionExists = await supabaseStore.sessionExists({ session: sessionName });
    if (sessionExists && remoteSessionSaved) {
      console.log(`[${instanceName}] ✅ Sesión ya existe en Supabase, no es necesario guardar manualmente`);
      return true;
    }

    console.warn(`[${instanceName}] 🔄 Iniciando guardado manual de sesión...`);
    await supabaseStore.save({ session: sessionName, path: sessionDir });

    console.warn(`[${instanceName}] ✅ Sesión guardada manualmente en Supabase Storage`);
    remoteSessionSaved = true;
    return true;
  } catch (error) {
    console.error(`[${instanceName}] ❌ Error guardando sesión manualmente:`, error.message);
    return false;
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

client.on('loading_screen', (percent, message) => {
  console.log(`[${instanceName}] Cargando WhatsApp: ${percent}% - ${message}`);
});

client.on('qr', qr => {
  console.warn(`[${instanceName}] QR Code recibido, generándolo en terminal y guardándolo...`);
  qrcode.generate(qr, { small: true });
  qrCodeData = qr; // Guardamos el QR para la API
  clientStatus = 'qr_ready';

  // Cancelar timer de detección (el QR llegó, la sesión está OK)
  if (sessionTimeout) {
    clearTimeout(sessionTimeout);
    sessionTimeout = null;
    sessionRetryCount = 0;
    console.log(`[${instanceName}] ✅ Sesión válida detectada - Temporizador cancelado`);
  }

  // Notificar a clientes WebSocket
  io.emit('status', {
    status: 'qr_ready',
    qr,
    timestamp: new Date().toISOString(),
  });
});

// Marcar como conectado al autenticarse (al escanear QR)
client.on('authenticated', () => {
  if (clientStatus !== 'connected') {
    console.warn(`[${instanceName}] Autenticación exitosa (authenticated)`);
    console.warn(`[${instanceName}] ⏳ Esperando a que el cliente esté completamente listo...`);
  }
  // NO establecer clientStatus = 'connected' aquí
  // Dejamos que el mecanismo de detección de estado lo haga
  qrCodeData = null;
  io.emit('status', { status: 'authenticated', timestamp: new Date().toISOString() });
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
  if (clientStatus !== 'connected') {
    console.warn(`[${instanceName}] ¡Cliente de WhatsApp está listo con sesión remota!`);
  }
  qrCodeData = null; // Ya no necesitamos el QR
  clientStatus = 'connected';

  // Cancelar timer de detección de sesión corrupta
  if (sessionTimeout) {
    clearTimeout(sessionTimeout);
    sessionTimeout = null;
    sessionRetryCount = 0; // Resetear contador
    console.log(`[${instanceName}] ✅ Sesión válida detectada - Temporizador cancelado`);
  }

  // Notificar a clientes WebSocket
  io.emit('status', {
    status: 'connected',
    timestamp: new Date().toISOString(),
  });
});

client.on('remote_session_saved', () => {
  remoteSessionSaved = true;
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
  console.warn('  tipo:', message.type, 'tieneUbicacion:', !!message.location);

  // Depuración avanzada para ubicaciones
  if (message.type === 'location' || message.type === 'live_location') {
    console.warn('🔍 Detalles del mensaje de ubicación:');
    console.warn('  - type:', message.type);
    console.warn('  - hasMedia:', message.hasMedia);
    console.warn('  - location type:', typeof message.location);
    if (message.location) {
      console.warn('  - location keys:', Object.keys(message.location));
      console.warn('  - location completo:', JSON.stringify(message.location, null, 2));
    }
    console.warn('  - body length:', message.body ? message.body.length : 0);
    console.warn(
      '  - body preview:',
      message.body ? message.body.substring(0, 100) + '...' : '[none]'
    );
  }

  if (message.hasQuotedMsg) {
    try {
      const quoted = await message.getQuotedMessage();
      console.warn('  quoted body:', quoted && quoted.body ? quoted.body : '[none]');
    } catch {}
  }

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

  // Procesar con IA y responder (soporta UI estructurada)
  try {
    // Ignorar tipos de mensaje no conversacionales (evita respuestas a notificaciones/templates)
    const allowedTypes = new Set(['chat', 'location', 'live_location']);
    if (!allowedTypes.has(message.type)) {
      console.warn('  [ignorado] tipo no conversacional:', message.type);
      return;
    }

    const ai = await processWithAI(message);
    try {
      console.warn('AI raw:', JSON.stringify(ai).slice(0, 500));
    } catch {}

    async function sendAiObject(obj) {
      const text = obj.ai_response || obj.response || obj.text;
      const ui = obj.ui || {};
      const mediaUrl = obj.media_url || obj.image_url || (obj.media && obj.media.url);
      const mediaCaption = obj.media_caption || obj.caption || text;
      let mediaSent = false;

      if (mediaUrl) {
        try {
          await sendMedia(message.from, mediaUrl, mediaCaption);
          mediaSent = true;
        } catch (err) {
          console.error('No se pudo enviar la foto (media):', err?.message || err);
        }
      }

      if (ui.type === 'buttons' && Array.isArray(ui.buttons)) {
        await sendButtons(message.from, text || 'Elige una opción:', ui.buttons);
        console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
        return;
      } else if (ui.type === 'location_request') {
        await sendText(
          message.from,
          text || 'Por favor comparte tu ubicación 📎 para mostrarte los más cercanos.'
        );
        console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
        return;
      } else if (ui.type === 'provider_results') {
        try {
          const names = (ui.providers || []).map(p => p.name || 'Proveedor');
          console.warn('➡️ Enviando provider_results al usuario:', { count: names.length, names });
        } catch {}
        await sendProviderResults(
          message.from,
          text || 'Encontré estas opciones:',
          ui.providers || []
        );
        console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
        return;
      } else if (ui.type === 'feedback' && Array.isArray(ui.options)) {
        await sendButtons(message.from, text || 'Califica tu experiencia:', ui.options);
        console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
        return;
      } else if (ui.type === 'silent') {
        return;
      }

      if (mediaSent && (!text || mediaCaption === text)) {
        console.warn('Respuesta enviada (IA): media');
        return;
      }

      if (mediaSent && text && mediaCaption !== text) {
        await sendText(message.from, text);
        console.warn('Respuesta enviada (IA): media + texto');
        return;
      }

      if (text) {
        await sendText(message.from, text);
        console.warn('Respuesta enviada (IA):', text || ui.type || '[sin texto]');
      } else {
        await sendText(message.from, 'Procesando tu mensaje...');
        console.warn('Respuesta enviada (IA): procesamiento');
      }
    }

    // Permitir múltiples mensajes en una sola respuesta de IA
    if (Array.isArray(ai.messages) && ai.messages.length > 0) {
      for (const m of ai.messages) {
        await sendAiObject(m || {});
      }
    } else {
      await sendAiObject(ai || {});
    }
  } catch (error) {
    console.error('Error al procesar mensaje:', error);
    // Enviar respuesta de fallback solo si falla la IA
    await sendText(
      message.from,
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

// Verificar estado del cliente independientemente de los eventos (workaround para RemoteAuth)
let readyManuallyEmitted = false;
let stateCheckFailures = 0;
const MAX_STATE_CHECK_FAILURES = 5;

const stateCheckInterval = setInterval(async () => {
  try {
    const state = await client.getState();

    // Resetear contador de fallos si tenemos éxito
    stateCheckFailures = 0;

    if (state && !readyManuallyEmitted && clientStatus !== 'connected') {
      console.log(`[${instanceName}] 🔍 Estado actual: ${state}`);
    }

    const validStates = ['CONNECTED', 'AUTHENTICATED'];
    const isValidState = validStates.includes(state);

    if (isValidState && !readyManuallyEmitted && clientStatus !== 'connected') {
      console.log(`[${instanceName}] ✅ Estado detectado: ${state} - Cliente está listo (sin evento ready)`);

      readyManuallyEmitted = true;

      if (sessionTimeout) {
        clearTimeout(sessionTimeout);
        sessionTimeout = null;
        sessionRetryCount = 0;
      }

      clientStatus = 'connected';
      qrCodeData = null;

      io.emit('status', {
        status: 'connected',
        timestamp: new Date().toISOString(),
      });

      clearInterval(stateCheckInterval);
      console.log(`[${instanceName}] ✅ Listener de mensajes activado`);

      // Programar guardado manual si RemoteAuth no lo hace
      if (!remoteSessionSaved) {
        console.log(`[${instanceName}] ⏰ Programando guardado manual de sesión en ${MANUAL_SAVE_DELAY_MS / 1000}s...`);
        setTimeout(async () => {
          if (!remoteSessionSaved) {
            console.warn(`[${instanceName}] ⚠️ RemoteAuth no guardó la sesión, ejecutando guardado manual...`);
            await guardarSesionManualmente();
          }
        }, MANUAL_SAVE_DELAY_MS);
      }
    }
  } catch (err) {
    stateCheckFailures++;
    const errorMsg = err?.message || err;

    // Si el error es "Cannot read properties of null (reading 'evaluate')"
    // es un problema conocido de Puppeteer/RemoteAuth - intentar forzar el estado
    if (errorMsg.includes('evaluate') || errorMsg.includes('null')) {
      if (!readyManuallyEmitted && clientStatus !== 'connected') {
        console.log(`[${instanceName}] ⚠️ Error Puppeteer conocido (${stateCheckFailures}/${MAX_STATE_CHECK_FAILURES})`);

        // Si hemos tenido varios fallos consecutivos y estamos en 'authenticated',
        // asumir que el cliente está listo
        if (stateCheckFailures >= MAX_STATE_CHECK_FAILURES) {
          console.warn(`[${instanceName}] ⚠️ Forzando estado 'connected' debido a bug de Puppeteer`);

          readyManuallyEmitted = true;

          if (sessionTimeout) {
            clearTimeout(sessionTimeout);
            sessionTimeout = null;
            sessionRetryCount = 0;
          }

          clientStatus = 'connected';
          qrCodeData = null;

          io.emit('status', {
            status: 'connected',
            timestamp: new Date().toISOString(),
          });

          clearInterval(stateCheckInterval);
          console.log(`[${instanceName}] ✅ Cliente marcado como listo (workaround aplicado)`);
        }
      }
    } else if (!readyManuallyEmitted && clientStatus !== 'connected') {
      console.log(`[${instanceName}] ⚠️ Error obteniendo estado: ${errorMsg}`);
    }
  }
}, 3000);

// Detener verificaciones después de 5 minutos
setTimeout(() => {
  if (!readyManuallyEmitted) {
    console.warn(`[${instanceName}] ⚠️ Timeout de verificación de estado sin detectar conexión.`);
  }
  clearInterval(stateCheckInterval);
}, 300000);

// Guardado periódico de sesión como fallback (cada 5 minutos)
setInterval(async () => {
  if (clientStatus === 'connected' && !remoteSessionSaved) {
    console.warn(`[${instanceName}] 🔄 Ejecutando guardado periódico de sesión...`);
    await guardarSesionManualmente();
  }
}, 300000);

// Función para detectar sesión corrupta y reiniciar timer
function iniciarDeteccionSesionCorrupta() {
  console.log(`[${instanceName}] 🕐 Temporizador de detección de sesión corrupta iniciado (60s)`);

  sessionTimeout = setTimeout(async () => {
    // Si después de 60s no hay QR ni ready, la sesión está corrupta
    if (clientStatus === 'disconnected' && !qrCodeData) {
      console.error(`[${instanceName}] ⚠️ Sesión corrupta detectada - Iniciando auto-limpieza...`);

      if (sessionRetryCount < MAX_SESSION_RETRIES) {
        sessionRetryCount++;
        console.log(`[${instanceName}] 🧹 Auto-limpieza de sesión corrupta (intento ${sessionRetryCount}/${MAX_SESSION_RETRIES})`);

        await resetWhatsAppSession('auto-corrupt-session', {
          attemptLogout: true,
          forceDeleteSession: true
        });

        // Reiniciar el cliente después de la limpieza
        await new Promise(resolve => setTimeout(resolve, 2000));
        client.initialize();

        // Reiniciar el timer llamando a la función nuevamente
        iniciarDeteccionSesionCorrupta();
      } else {
        console.error(`[${instanceName}] ❌ Máximo de reintentos alcanzado. Sesión permanentemente corrupta.`);
        clientStatus = 'session_corrupted';
      }
    }
  }, 60000); // 60 segundos
}

// Iniciar el timer de detección
iniciarDeteccionSesionCorrupta();

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
  const statusData = {
    status: clientStatus,
    sessionRetryCount,
    maxRetries: MAX_SESSION_RETRIES
  };

  if (clientStatus === 'session_corrupted') {
    statusData.message = 'La sesión está permanentemente corrupta. Elimina manualmente el archivo de Supabase Storage.';
  }

  res.json(statusData);
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

  // Verificar conexión con AI Service Clientes
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
