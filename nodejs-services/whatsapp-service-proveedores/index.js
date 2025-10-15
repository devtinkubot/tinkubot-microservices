const express = require('express');
const { Client, RemoteAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const cors = require('cors');
const axios = require('axios');
const http = require('http');
const { Server } = require('socket.io');
const SupabaseStore = require('./SupabaseStore');

const app = express();
const port = process.env.WHATSAPP_PORT || 7002;
const instanceId = 'bot-proveedores';
const instanceName = 'TinkuBot Proveedores';

// Configuración de servicios externos
// ESPECIALIZADO: Siempre usa el AI Service Proveedores
const AI_SERVICE_URL =
  process.env.PROVEEDORES_AI_SERVICE_URL || 'http://ai-service-proveedores:5002';

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

// Función para procesar mensajes con IA
// ACTUALIZADO: Ahora usa el endpoint /handle-whatsapp-message que incluye gestión de sesiones
async function processWithAI(message) {
  try {
    // Verificar si el mensaje tiene texto o es multimedia
    const messageText = message.body;

    // Si no hay texto, manejar según el tipo de mensaje
    if (!messageText || messageText.trim() === '') {
      if (message.hasMedia) {
        // Para mensajes multimedia, usar una respuesta genérica
        return 'He recibido tu archivo multimedia. Por favor, envía un mensaje de texto para que pueda ayudarte mejor.';
      } else {
        // Para otros tipos de mensajes sin texto
        return 'Lo siento, solo puedo procesar mensajes de texto. Por favor, envía tu consulta en formato de texto.';
      }
    }

    // ACTUALIZADO: Usar el endpoint del servicio IA correspondiente
    const response = await axios.post(`${AI_SERVICE_URL}/handle-whatsapp-message`, {
      id: message.id._serialized || message.id,
      from_number: message.from,
      content: messageText,
      timestamp: new Date(),
      status: 'received',
    });

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
  console.warn(`[${instanceName}] Sesión guardada en Supabase Storage`);
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
    const responses = await processWithAI(message);
    const replies = Array.isArray(responses) ? responses : [responses];

    for (const replyText of replies) {
      if (!replyText || typeof replyText !== 'string') continue;
      await message.reply(replyText);
      console.warn('Respuesta enviada:', replyText);
    }
  } catch (error) {
    console.error('Error al procesar mensaje:', error);
    // Enviar respuesta de fallback solo si falla la IA
    await message.reply(
      'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.'
    );
  }
});

client.on('disconnected', reason => {
  console.error(`[${instanceName}] Cliente desconectado:`, reason);
  clientStatus = 'disconnected';

  // Notificar a clientes WebSocket
  io.emit('status', {
    status: 'disconnected',
    reason,
    timestamp: new Date().toISOString(),
  });

  // Opcional: intentar reinicializar
  // client.initialize();
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
