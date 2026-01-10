const express = require('express');
const { Client, MessageMedia, RemoteAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const container = require('./container');

// Inicializar contenedor de dependencias
container.initialize();

const config = container.config;
const port = config.port;
const instanceId = config.instanceId;
const instanceName = config.instanceName;
const REQUEST_TIMEOUT_MS = config.requestTimeoutMs;
const supabaseStore = container.supabaseStore;
const aiServiceClient = container.aiServiceClient;
const mqttClient = container.mqttClient;
const handlerRegistry = container.handlerRegistry;

// Configuración de instancia
const startupInfo = config.getStartupInfo();
console.warn(`🤖 Iniciando ${startupInfo.instanceName} (ID: ${startupInfo.instanceId})`);
console.warn(`📱 Puerto: ${startupInfo.port}`);
console.warn(`📡 MQTT disponibilidad: ${startupInfo.mqtt}`);

// Variables de estado del cliente
let qrCodeData = null;
let clientStatus = 'disconnected';
let isRefreshing = false;
let lastSessionSavedLog = 0;
const SESSION_LOG_INTERVAL_MS = 5 * 60 * 1000;

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

// Registrar cliente en el contenedor
container.registerWhatsAppClient(client);

// Crear aplicación Express con todas las rutas y middleware
const runtimeServices = {
  clientStatus,
  qrCodeData,
  resetWhatsAppSession
};
const app = container.createExpressApp(runtimeServices);

// Configurar servidor HTTP y WebSocket
const server = container.createHttpServer();
const socketServer = container.createSocketServer();
console.warn(`✅ HandlerRegistry inicializado con ${handlerRegistry.count} handler(s)`);
console.warn(`✅ MQTT Client inicializado`);

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

// Conectar MQTT para disponibilidad de proveedores
mqttClient.connect();

// Iniciar servidor
server.listen(port, () => {
  console.warn(`🚀 ${instanceName} (ID: ${instanceId}) escuchando en http://localhost:${port}`);
  console.warn('🔌 WebSocket habilitado para notificaciones en tiempo real');
});
