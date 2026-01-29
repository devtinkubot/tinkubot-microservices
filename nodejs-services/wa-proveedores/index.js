const express = require('express');
const { Client, RemoteAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const cors = require('cors');
const axios = require('axios');
const mqtt = require('mqtt');
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

// MQTT para disponibilidad de proveedores
const mqttHost = process.env.MQTT_HOST || 'mosquitto';
const mqttPort = parseInt(process.env.MQTT_PORT || '1883', 10);
const mqttUsuario = process.env.MQTT_USUARIO;
const mqttPassword = process.env.MQTT_PASSWORD;
const mqttTemaSolicitud = process.env.MQTT_TEMA_SOLICITUD || 'av-proveedores/solicitud';
const mqttTemaRespuesta = process.env.MQTT_TEMA_RESPUESTA || 'av-proveedores/respuesta';
const mqttTemaAprobado = process.env.MQTT_TEMA_PROVEEDOR_APROBADO || 'providers/approved';
const mqttTemaRechazado = process.env.MQTT_TEMA_PROVEEDOR_RECHAZADO || 'providers/rejected';
const MAX_RESPUESTAS_DISPONIBILIDAD = 5;

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
const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
const supabaseBucket = process.env.SUPABASE_BUCKET_NAME;
const supabaseProvidersTable = process.env.SUPABASE_PROVIDERS_TABLE || 'providers';

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
console.warn(
  `📡 MQTT disponibilidad: host=${mqttHost}:${mqttPort} tema_solicitud=${mqttTemaSolicitud} tema_respuesta=${mqttTemaRespuesta} tema_aprobado=${mqttTemaAprobado}`
);

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

// Variables para tracking de guardado de sesión RemoteAuth
let remoteSessionSaved = false;
const MANUAL_SAVE_DELAY_MS = 90000; // 90 segundos - tiempo para que RemoteAuth haga su trabajo

// Variables para auto-detección de sesión corrupta
let sessionTimeout = null;
let sessionRetryCount = 0;
const MAX_SESSION_RETRIES = 2;

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

function normalizarNumeroWhatsApp(numero) {
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
    // Celular de Ecuador sin prefijo
    normalizado = `593${normalizado}`;
  }

  if (!normalizado.startsWith('593')) {
    console.warn(`⚠️ Número sin prefijo de país, se usa tal cual: ${normalizado}`);
  }

  return `${normalizado}@c.us`;
}

function esLidWhatsApp(valor) {
  if (!valor) return false;
  return String(valor).trim().endsWith('@lid');
}

// --- MQTT helper para disponibilidad ---
const mqttOptions = {};
if (mqttUsuario && mqttPassword) {
  mqttOptions.username = mqttUsuario;
  mqttOptions.password = mqttPassword;
}

let mqttClient = null;
// solicitudesActivas: providerPhone -> { reqId, providerId, expiresAt, timer }
const solicitudesActivas = new Map();
// solicitudesPorReq: reqId -> Set(providerPhone)
const solicitudesPorReq = new Map();
// respuestasPorReq: reqId -> count de aceptadas
const respuestasPorReq = new Map();

function conectarMqtt() {
  try {
    const url = `mqtt://${mqttHost}:${mqttPort}`;
    mqttClient = mqtt.connect(url, mqttOptions);

    mqttClient.on('connect', () => {
      console.warn(`📡 MQTT conectado a ${url}`);
      mqttClient.subscribe(mqttTemaSolicitud, err => {
        if (err) {
          console.error('❌ No se pudo suscribir a solicitudes:', err.message || err);
        } else {
          console.warn(`✅ Suscrito a ${mqttTemaSolicitud}`);
        }
      });
      mqttClient.subscribe(mqttTemaAprobado, err => {
        if (err) {
          console.error('❌ No se pudo suscribir a aprobaciones:', err.message || err);
        } else {
          console.warn(`✅ Suscrito a ${mqttTemaAprobado}`);
        }
      });
      mqttClient.subscribe(mqttTemaRechazado, err => {
        if (err) {
          console.error('❌ No se pudo suscribir a rechazos:', err.message || err);
        } else {
          console.warn(`✅ Suscrito a ${mqttTemaRechazado}`);
        }
      });
    });

    mqttClient.on('error', err => {
      console.error('❌ Error MQTT:', err.message || err);
    });

    mqttClient.on('message', async (topic, message) => {
      try {
        if (topic === mqttTemaSolicitud) {
          const data = JSON.parse(message.toString());
          await manejarSolicitudDisponibilidad(data);
          return;
        }
        if (topic === mqttTemaAprobado) {
          const data = JSON.parse(message.toString());
          await manejarAprobacionProveedor(data);
          return;
        }
        if (topic === mqttTemaRechazado) {
          const data = JSON.parse(message.toString());
          await manejarRechazoProveedor(data);
          return;
        }
      } catch (err) {
        console.error('❌ Error procesando mensaje MQTT:', err.message || err);
      }
    });
  } catch (err) {
    console.error('❌ No se pudo inicializar MQTT:', err.message || err);
  }
}

function formatearTiempo(segundos) {
  const s = Number(segundos) || 0;
  if (s >= 60) {
    const mins = Math.round(s / 60);
    return `${mins} minuto${mins === 1 ? '' : 's'}`;
  }
  return `${s} segundo${s === 1 ? '' : 's'}`;
}

function registrarSolicitud(reqId, phone, expiresAt, providerId) {
  const current = solicitudesPorReq.get(reqId) || new Set();
  current.add(phone);
  solicitudesPorReq.set(reqId, current);
  const timer = setTimeout(async () => {
    const active = solicitudesActivas.get(phone);
    if (!active || active.reqId !== reqId) return;
    solicitudesActivas.delete(phone);
    current.delete(phone);
    if (current.size === 0) {
      solicitudesPorReq.delete(reqId);
    }
    try {
      await enviarTextoWhatsApp(
        phone,
        '*El tiempo de respuesta ha caducado y tu respuesta ya no contará para este requerimiento.*'
      );
    } catch (err) {
      console.error(`❌ No se pudo notificar expiración a ${phone}:`, err.message || err);
    }
  }, Math.max(1000, expiresAt - Date.now()));

  solicitudesActivas.set(phone, { reqId, providerId, expiresAt, timer });
}

async function manejarSolicitudDisponibilidad(data) {
  const reqId = data.req_id || 'sin-id';
  const servicio = data.servicio || 'servicio';
    const ciudad = data.ciudad || '';
  const candidatos = Array.isArray(data.candidatos) ? data.candidatos : [];
  const timeoutSeg = Number(data.tiempo_espera_segundos) || 60;
  const textoTiempo = formatearTiempo(timeoutSeg);

  for (const cand of candidatos) {
    const phoneRaw = cand.phone || cand.phone_number || cand.contact || cand.contact_phone;
    const phone = normalizarNumeroWhatsApp(phoneRaw);
    if (!phone) {
      console.warn(`⚠️ Candidato sin número válido: ${JSON.stringify(cand)}`);
      continue;
    }
    solicitudesActivas.set(phone, { reqId, providerId: cand.id || cand.provider_id || null });
    const providerName =
      cand.name || cand.provider_name || cand.nombre || cand.display_name || 'Proveedor';
    const ciudadTexto = (ciudad || '').trim();
    const ubicacion = ciudadTexto ? ` en **${ciudadTexto}**` : '';
    const expiresAt = Date.now() + timeoutSeg * 1000;
    registrarSolicitud(reqId, phone, expiresAt, cand.id || cand.provider_id || null);
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
      await enviarTextoWhatsApp(phone, textoPregunta);
      await enviarTextoWhatsApp(phone, textoOpciones);
      console.warn(`📨 Ping disponibilidad enviado a ${phone} req=${reqId}`);
    } catch (err) {
      console.error(`❌ No se pudo enviar ping a ${phone}:`, err.message || err);
    }
  }
}

async function publicarRespuestaDisponibilidad(reqId, providerId, estado) {
  if (!mqttClient || !mqttClient.connected) return;
  const payload = JSON.stringify({ req_id: reqId, provider_id: providerId, estado });
  mqttClient.publish(mqttTemaRespuesta, payload, err => {
    if (err) {
      console.error('❌ No se pudo publicar respuesta MQTT:', err.message || err);
    } else {
      console.warn(`📤 Respuesta disponibilidad publicada req=${reqId} provider=${providerId} estado=${estado}`);
    }
  });
}

async function enviarTextoWhatsApp(numero, texto) {
  const destino = normalizarNumeroWhatsApp(numero);
  if (!destino) {
    throw new Error(`Número de WhatsApp inválido: ${numero}`);
  }
  const contenido = texto || ' ';
  return client.sendMessage(destino, contenido);
}

const supabaseRest = axios.create({
  baseURL: `${supabaseUrl.replace(/\/$/, '')}/rest/v1`,
  headers: {
    apikey: supabaseKey,
    Authorization: `Bearer ${supabaseKey}`,
    'Content-Type': 'application/json',
    Prefer: 'return=minimal',
  },
  timeout: 5000,
});

async function marcarAprobacionNotificada(providerId) {
  if (!providerId) return;
  try {
    const fecha = new Date().toISOString();
    await supabaseRest.patch(
      `/${supabaseProvidersTable}?id=eq.${providerId}`,
      { approved_notified_at: fecha }
    );
    console.warn(`🗂️ approved_notified_at registrado en Supabase para ${providerId}`);
  } catch (err) {
    console.error(
      `⚠️ No se pudo registrar approved_notified_at para ${providerId}:`,
      err.message || err
    );
  }
}

function construirMensajeAprobacion(nombre) {
  const nombreCorto = (nombre || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .join(' ');
  const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
  return `${saludo} ✅ tu perfil está aprobado. Bienvenido/a a TinkuBot; permanece pendiente de las próximas solicitudes.`;
}

function construirMensajeRestriccionPais(nombre) {
  const nombreCorto = (nombre || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .join(' ');
  const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
  return `${saludo} 🌎 Gracias por tu interés en TinkuBot. Por el momento, el registro de proveedores está disponible solo para números nacionales de Ecuador. Si tienes un número ecuatoriano, por favor regístrate con ese número para continuar.`;
}

function construirMensajeRechazo(nombre, notas) {
  const nombreCorto = (nombre || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .join(' ');
  const saludo = nombreCorto ? `Hola ${nombreCorto},` : 'Hola,';
  const motivo = notas && String(notas).trim().length > 0 ? ` Motivo: ${notas}` : '';
  return `${saludo} 🚫 tu registro fue revisado y requiere ajustes.${motivo} Puedes actualizar tus datos y volver a enviarlos cuando estés listo.`;
}

async function manejarAprobacionProveedor(data) {
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
    if (!esLidWhatsApp(phone) && !soloDigitos.startsWith('593')) {
      // 📧 Enviar notificación de solo números nacionales
      const mensajeNotificacion = construirMensajeRestriccionPais(fullName);
      await enviarTextoWhatsApp(phone, mensajeNotificacion);

      console.warn(`⚠️ Intento de aprobación con número no ecuatoriano ${phone} - notificación enviada (provider_id=${providerId || 'n/a'})`);

      // Marcar como notificado para evitar reintentos
      if (providerId) {
        await marcarAprobacionNotificada(providerId);
      }
      return;
    }

    // ✅ Número ecuatoriano válido - enviar aprobación normal
    const mensajeAprobacion = construirMensajeAprobacion(fullName);
    await enviarTextoWhatsApp(phone, mensajeAprobacion);
    console.warn(`✅ Notificación de aprobación enviada a ${phone} (provider_id=${providerId || 'n/a'})`);

    if (providerId) {
      await marcarAprobacionNotificada(providerId);
    }
  } catch (err) {
    console.error(
      `❌ Error enviando notificación de aprobación a ${phone}:`,
      err.message || err
    );
  }
}

async function manejarRechazoProveedor(data) {
  const providerId = data?.provider_id || data?.id;
  const phone = data?.phone;
  const fullName = data?.full_name || '';
  const notes = data?.notes;

  if (!phone) {
    console.warn('⚠️ Evento de rechazo sin teléfono, se ignora');
    return;
  }

  try {
    const mensaje = construirMensajeRechazo(fullName, notes);
    await enviarTextoWhatsApp(phone, mensaje);
    console.warn(
      `✅ Notificación de rechazo enviada a ${phone} (provider_id=${providerId || 'n/a'})`
    );
  } catch (err) {
    console.error(
      `❌ Error enviando notificación de rechazo a ${phone}:`,
      err.message || err
    );
  }
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
 * Esto es un workaround para el bug donde el evento 'ready' no se dispara
 */
async function guardarSesionManualmente() {
  const sessionName = `RemoteAuth-${instanceId}`;
  const sessionDir = `/app/.wwebjs_auth/${sessionName}`;

  try {
    const fs = require('fs-extra');
    const pathExists = await fs.pathExists(sessionDir);

    if (!pathExists) {
      console.warn(`[${instanceName}] Directorio de sesión no encontrado: ${sessionDir}`);
      return false;
    }

    // Verificar si ya existe una sesión guardada recientemente
    const sessionExists = await supabaseStore.sessionExists({ session: sessionName });
    if (sessionExists && remoteSessionSaved) {
      console.log(`[${instanceName}] Sesión ya existe en Supabase, no es necesario guardar manualmente`);
      return true;
    }

    console.warn(`[${instanceName}] Iniciando guardado manual de sesión...`);

    // Guardar usando el store directamente
    await supabaseStore.save({ session: sessionName, path: sessionDir });

    console.warn(`[${instanceName}] Sesión guardada manualmente en Supabase Storage`);
    remoteSessionSaved = true;
    return true;
  } catch (error) {
    console.error(`[${instanceName}] Error guardando sesión manualmente:`, error.message);
    return false;
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
  remoteSessionSaved = true;  // Marcar que RemoteAuth sí guardó la sesión
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

  // Responder solicitudes de disponibilidad sin pasar por IA
  const solicitud = solicitudesActivas.get(message.from);
  if (solicitud) {
    const opcion = (message.body || '').trim().toLowerCase();
    const isYes = opcion === '1' || opcion === 'si' || opcion === 'sí';
    const ahora = Date.now();
    const chat = await message.getChat();
    const reqId = solicitud.reqId;

    // Si la solicitud ya expiró
    if (solicitud.expiresAt && ahora > solicitud.expiresAt) {
      solicitudesActivas.delete(message.from);
      const setReq = solicitudesPorReq.get(reqId);
      if (setReq) {
        setReq.delete(message.from);
        if (setReq.size === 0) solicitudesPorReq.delete(reqId);
      }
      await chat.sendMessage(
        '*El tiempo de respuesta ha caducado y tu respuesta ya no contará para este requerimiento.*'
      );
      return;
    }

    // Control de cupo máximo
    const aceptadasPrevias = respuestasPorReq.get(reqId) || 0;
    if (aceptadasPrevias >= MAX_RESPUESTAS_DISPONIBILIDAD) {
      solicitudesActivas.delete(message.from);
      const setReq = solicitudesPorReq.get(reqId);
      if (setReq) {
        setReq.delete(message.from);
        if (setReq.size === 0) solicitudesPorReq.delete(reqId);
      }
      await chat.sendMessage('*Las plazas para este requerimiento ya han sido ocupadas.*');
      return;
    }

    const estado = isYes ? 'accepted' : 'declined';
    try {
      await publicarRespuestaDisponibilidad(reqId, solicitud.providerId, estado);
    } catch (err) {
      console.error('❌ No se pudo publicar respuesta de disponibilidad:', err.message || err);
    }
    solicitudesActivas.delete(message.from);
    const setReq = solicitudesPorReq.get(reqId);
    if (setReq) {
      setReq.delete(message.from);
      if (setReq.size === 0) solicitudesPorReq.delete(reqId);
    }

    if (isYes) {
      const nuevoConteo = aceptadasPrevias + 1;
      respuestasPorReq.set(reqId, nuevoConteo);

      await chat.sendMessage('*Gracias, tomamos nota de tu disponibilidad.*');

      if (nuevoConteo >= MAX_RESPUESTAS_DISPONIBILIDAD && setReq && setReq.size > 0) {
        // Notificar a pendientes que ya no hay cupo
        const pendientes = Array.from(setReq);
        solicitudesPorReq.delete(reqId);
        for (const phone of pendientes) {
          solicitudesActivas.delete(phone);
          try {
            await enviarTextoWhatsApp(
              phone,
              '*Las plazas para este requerimiento ya han sido ocupadas.*'
            );
          } catch (err) {
            console.error(`❌ No se pudo notificar cierre de cupo a ${phone}:`, err.message || err);
          }
        }
      }
    } else {
      await chat.sendMessage('*Entendido, registramos que no estás disponible para esta solicitud.*');
    }
    return;
  }

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

// Guardado periódico de sesión como fallback (cada 5 minutos)
setInterval(async () => {
  if (clientStatus === 'connected' && !remoteSessionSaved) {
    console.warn(`[${instanceName}] Ejecutando guardado periódico de sesión...`);
    await guardarSesionManualmente();
  }
}, 300000); // 5 minutos

// Verificar estado del cliente independientemente de los eventos (porque ready no se dispara con RemoteAuth)
let readyManuallyEmitted = false;
let stateCheckFailures = 0;
const MAX_STATE_CHECK_FAILURES = 5;

const stateCheckInterval = setInterval(async () => {
  try {
    const state = await client.getState();

    // Resetear contador de fallos si tenemos éxito
    stateCheckFailures = 0;

    // Log de depuración para ver qué estado se está devolviendo
    if (state && !readyManuallyEmitted && clientStatus !== 'connected') {
      console.log(`[${instanceName}] 🔍 Estado actual: ${state}`);
    }

    // Aceptar estados válidos: CONNECTED o AUTHENTICATED (para RemoteAuth)
    const validStates = ['CONNECTED', 'AUTHENTICATED'];
    const isValidState = validStates.includes(state);

    if (isValidState && !readyManuallyEmitted && clientStatus !== 'connected') {
      console.log(`[${instanceName}] Estado detectado: ${state} - Cliente está listo (sin evento ready)`);

      readyManuallyEmitted = true;

      // Cancelar timer de detección de sesión corrupta
      if (sessionTimeout) {
        clearTimeout(sessionTimeout);
        sessionTimeout = null;
        sessionRetryCount = 0;
      }

      clientStatus = 'connected';
      qrCodeData = null;

      // Notificar a clientes WebSocket
      io.emit('status', {
        status: 'connected',
        timestamp: new Date().toISOString(),
      });

      clearInterval(stateCheckInterval);
      console.log(`[${instanceName}] Listener de mensajes activado`);

      // Programar guardado manual si RemoteAuth no lo hace
      if (!remoteSessionSaved) {
        console.log(`[${instanceName}] Programando guardado manual de sesión en ${MANUAL_SAVE_DELAY_MS / 1000}s...`);
        setTimeout(async () => {
          if (!remoteSessionSaved) {
            console.warn(`[${instanceName}] RemoteAuth no guardó la sesión, ejecutando guardado manual...`);
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
}, 3000); // Verificar cada 3 segundos

// Detener verificaciones después de 5 minutos (aumentado de 2 minutos)
setTimeout(() => {
  if (!readyManuallyEmitted) {
    console.warn(`[${instanceName}] ⚠️ Timeout de verificación de estado sin detectar conexión. El bot puede no funcionar correctamente.`);
  }
  clearInterval(stateCheckInterval);
}, 300000); // 5 minutos

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

// --- Suscripción MQTT para disponibilidad ---
conectarMqtt();

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
