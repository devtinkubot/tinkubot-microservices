const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const axios = require('axios');
const path = require('path');
const QRCode = require('qrcode');
const fs = require('fs');
const http = require('http');
const https = require('https');
const adminProvidersRouter = require('./routes/adminProviders');
const session = require('express-session');
const app = express();

const ADMIN_USER = process.env.ADMIN_USER || 'hvillalba';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

const parsearPuerto = valor => {
  const numero = Number(valor);
  return Number.isFinite(numero) && numero > 0 ? numero : undefined;
};

const resolverPuerto = (valorPorDefecto, ...candidatos) => {
  for (const candidato of candidatos) {
    const puerto = parsearPuerto(candidato);
    if (puerto !== undefined) {
      return puerto;
    }
  }
  return valorPorDefecto;
};

// Configuración
const PORT = resolverPuerto(5000, process.env.FRONTEND_SERVICE_PORT);
const clientesPort = resolverPuerto(
  5001,
  process.env.CLIENTES_WHATSAPP_PORT,
  process.env.WHATSAPP_CLIENTES_PORT
);
const proveedoresPort = resolverPuerto(
  5002,
  process.env.PROVEEDORES_WHATSAPP_PORT,
  process.env.WHATSAPP_PROVEEDORES_PORT
);

const serverDomain = process.env.SERVER_DOMAIN;
const clientesHost = serverDomain || 'wa-clientes';
const proveedoresHost = serverDomain || 'wa-proveedores';
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS || '8000', 10);
const STATIC_MAX_AGE_SECONDS = parseInt(process.env.STATIC_MAX_AGE_SECONDS || '86400', 10);

const WHATSAPP_CLIENTES_URL =
  process.env.WHATSAPP_CLIENTES_URL || `http://${clientesHost}:${clientesPort}`;
const WHATSAPP_PROVEEDORES_URL =
  process.env.WHATSAPP_PROVEEDORES_URL || `http://${proveedoresHost}:${proveedoresPort}`;

const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 20 });
const httpsAgent = new https.Agent({ keepAlive: true, maxSockets: 20 });
const axiosClient = axios.create({
  httpAgent,
  httpsAgent,
  timeout: 5000
});

const CLIENTES_INSTANCE_ID = process.env.CLIENTES_INSTANCE_ID || 'bot-clientes';
const CLIENTES_INSTANCE_NAME = process.env.CLIENTES_INSTANCE_NAME || 'TinkuBot Clientes';
const PROVEEDORES_INSTANCE_ID =
  process.env.PROVEEDORES_INSTANCE_ID || 'bot-proveedores';
const PROVEEDORES_INSTANCE_NAME =
  process.env.PROVEEDORES_INSTANCE_NAME || 'TinkuBot Proveedores';

// WA-Gateway configuration
const WA_GATEWAY_URL = process.env.WA_GATEWAY_URL || 'http://wa-gateway:7000';

// Configuración de instancias
const WHATSAPP_INSTANCES = [
  {
    id: CLIENTES_INSTANCE_ID,
    name: CLIENTES_INSTANCE_NAME,
    url: WHATSAPP_CLIENTES_URL,
    port: clientesPort,
  },
  {
    id: PROVEEDORES_INSTANCE_ID,
    name: PROVEEDORES_INSTANCE_NAME,
    url: WHATSAPP_PROVEEDORES_URL,
    port: proveedoresPort,
  },
];

console.warn('🔧 Configuración de instancias:');
WHATSAPP_INSTANCES.forEach(instance => {
  console.warn(`  - ${instance.name}: ${instance.url}`);
});

const dashboardDistPath = path.join(__dirname, 'apps', 'admin-dashboard', 'dist');
const publicPath = path.join(__dirname, 'public');

const existeCompilacionDashboard = () => fs.existsSync(path.join(dashboardDistPath, 'index.html'));

if (fs.existsSync(dashboardDistPath)) {
  console.warn(`🧱 Dashboard compilado encontrado en: ${dashboardDistPath}`);
} else {
  console.warn('⚠️ No se encontró build del dashboard, sirviendo versión legacy desde /public.');
}

// Autenticación HTTP básica (protege UI y APIs). Requiere ADMIN_PASSWORD.
const authEnabled = !!ADMIN_PASSWORD;
if (authEnabled) {
  console.warn('🔒 Autenticación básica habilitada para el panel.');
} else {
  console.warn('⚠️ ADMIN_PASSWORD no configurado; panel sin autenticación.');
}

const basicAuth = (req, res, next) => {
  if (!authEnabled) return next();
  if (req.path === '/health') return next();

  const header = req.headers.authorization || '';
  const [scheme, encoded] = header.split(' ');
  if (scheme === 'Basic' && encoded) {
    try {
      const decoded = Buffer.from(encoded, 'base64').toString();
      const [user, pass] = decoded.split(':');
      if (user === ADMIN_USER && pass === ADMIN_PASSWORD) {
        return next();
      }
    } catch (err) {
      console.warn('Error decodificando cabecera Authorization:', err.message || err);
    }
  }
  res.set('WWW-Authenticate', 'Basic realm="TinkuBot Admin"');
  return res.status(401).send('Autenticación requerida');
};

// Middleware
app.use(compression());
app.use(helmet({
  contentSecurityPolicy: false,
  crossOriginEmbedderPolicy: false
}));
app.use(
  rateLimit({
    windowMs: 60 * 1000,
    max: parseInt(process.env.RATE_LIMIT_MAX || '120', 10),
    standardHeaders: true,
    legacyHeaders: false
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

// Configurar sesión
app.use(session({
  secret: process.env.SESSION_SECRET || 'tinkubot-secret-key-2024',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: false, // true si usas HTTPS
    maxAge: 24 * 60 * 60 * 1000, // 24 horas
    httpOnly: true
  }
}));

// Middleware de autenticación con sesiones
const requireAuth = (req, res, next) => {
  // Rutas públicas (sin autenticación)
  const publicPaths = ['/health', '/login', '/api/login', '/api/logout', '/api/auth/status', '/qr'];
  if (publicPaths.includes(req.path)) return next();

  // Verificar si está autenticado
  if (req.session && req.session.authenticated) return next();

  // Si no está autenticado y es una ruta de API, retornar 401
  if (req.path.startsWith('/api/')) {
    return res.status(401).json({ error: 'Autenticación requerida' });
  }

  // Para rutas de página, redirigir a login
  return res.redirect('/login');
};

app.use(requireAuth);
if (fs.existsSync(dashboardDistPath)) {
  app.use(
    express.static(dashboardDistPath, {
      maxAge: STATIC_MAX_AGE_SECONDS * 1000,
      etag: true,
      setHeaders: res => {
        res.setHeader('Cache-Control', `public, max-age=${STATIC_MAX_AGE_SECONDS}`);
      }
    })
  );
}
app.use(
  express.static(publicPath, {
    maxAge: STATIC_MAX_AGE_SECONDS * 1000,
    etag: true,
    setHeaders: res => {
      res.setHeader('Cache-Control', `public, max-age=${STATIC_MAX_AGE_SECONDS}`);
    }
  })
);
app.use(express.json());
app.use('/admin/providers', adminProvidersRouter);

// Health check para monitoreo básico
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    instances: WHATSAPP_INSTANCES.map(({ id, name, url }) => ({ id, name, url })),
    uptime_seconds: Math.round(process.uptime()),
  });
});

// API de login
app.post('/api/login', express.json(), (req, res) => {
  const { username, password } = req.body;

  // Verificar credenciales
  if (username === ADMIN_USER && password === ADMIN_PASSWORD) {
    req.session.authenticated = true;
    req.session.username = username;
    return res.json({ success: true, message: 'Login exitoso' });
  }

  return res.status(401).json({ success: false, message: 'Credenciales inválidas' });
});

// API de logout
app.post('/api/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      console.error('Error al cerrar sesión:', err);
      return res.status(500).json({ success: false, message: 'Error al cerrar sesión' });
    }
    res.clearCookie('connect.sid');
    return res.json({ success: true, message: 'Sesión cerrada' });
  });
});

// API para verificar autenticación
app.get('/api/auth/status', (req, res) => {
  res.json({
    authenticated: !!(req.session && req.session.authenticated),
    username: req.session ? req.session.username : null
  });
});

// Página de login
app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'login.html'));
});

// Rutas
app.get('/', (req, res) => {
  if (existeCompilacionDashboard()) {
    return res.sendFile(path.join(dashboardDistPath, 'index.html'));
  }
  return res.sendFile(path.join(publicPath, 'admin-dashboard.html'));
});

// API para obtener estado de WhatsApp por instancia
app.get('/api/whatsapp/:instanceId/status', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axiosClient.get(`${instance.url}/status`);
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al obtener estado de WhatsApp:', error);
    res.status(500).json({ error: 'Error al conectar con WhatsApp Service' });
  }
});

// API para obtener QR por instancia
app.get('/api/whatsapp/:instanceId/qr', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axiosClient.get(`${instance.url}/qr`);
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al obtener QR:', error);
    res.status(500).json({ error: 'Error al obtener QR de WhatsApp' });
  }
});

// API para enviar mensaje por instancia
app.post('/api/whatsapp/:instanceId/send', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const { phone, message } = req.body;
    if (!instanceId || typeof instanceId !== 'string') {
      return res.status(400).json({ error: 'Instancia inválida' });
    }
    if (typeof phone !== 'string' || typeof message !== 'string') {
      return res.status(400).json({ error: 'Parámetros inválidos' });
    }
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axiosClient.post(
      `${instance.url}/send`,
      { phone, message },
      { timeout: 5000 }
    );
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al enviar mensaje:', error);
    res.status(500).json({ error: 'Error al enviar mensaje' });
  }
});

app.post('/api/whatsapp/:instanceId/refresh', async (req, res) => {
  try {
    const { instanceId } = req.params;
    if (!instanceId || typeof instanceId !== 'string') {
      return res.status(400).json({ error: 'Instancia inválida' });
    }
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axiosClient.post(`${instance.url}/refresh`, null, { timeout: 5000 });
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al regenerar QR:', error?.message || error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al regenerar el código QR' };
    res.status(status).json(payload);
  }
});

// API para obtener estado de WhatsApp (simplificado)
app.get('/whatsapp-status', async (req, res) => {
  try {
    const statuses = {};

    const results = await Promise.allSettled(
      WHATSAPP_INSTANCES.map(async instance => {
        try {
          const statusResponse = await axiosClient.get(`${instance.url}/status`, { timeout: 3000 });
          const statusData = statusResponse.data;
          if (statusData.status === 'qr_ready') {
            let qrText;
            try {
              const qrResponse = await axiosClient.get(`${instance.url}/qr`, { timeout: 5000 });
              qrText = qrResponse.data.qr;
              const qrImage = await QRCode.toDataURL(qrText, {
                width: 300,
                margin: 2,
                color: {
                  dark: '#000000',
                  light: '#FFFFFF',
                },
              });
              return { instance, data: { connected: false, qr: qrImage, phone: null, battery: null } };
            } catch (qrError) {
              console.error(`Error al procesar QR de ${instance.name}:`, qrError);
              return { instance, data: { connected: false, qr: null, phone: null, battery: null } };
            }
          }
          if (statusData.status === 'connected' || statusData.connected) {
            return {
              instance,
              data: {
                connected: true,
                qr: null,
                phone: statusData.phone || null,
                battery: statusData.battery || null,
              },
            };
          }
          return { instance, data: { connected: false, qr: null, phone: null, battery: null } };
        } catch (error) {
          console.error(`Error al obtener estado de ${instance.name}:`, error);
          return { instance, data: { connected: false, qr: null, phone: null, battery: null } };
        }
      })
    );

    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { instance, data } = result.value;
        statuses[instance.id] = data;
      }
    }

    res.json(statuses);
  } catch (error) {
    console.error('Error al obtener estado de WhatsApp:', error);
    res.status(500).json({ error: 'Error al obtener estado de WhatsApp' });
  }
});

// ============================================================================
// WA-Gateway API Proxy (replaces wa-clientes/wa-proveedores)
// ============================================================================

// Proxy for GET /accounts
app.get('/api/accounts', async (req, res) => {
  try {
    const response = await axiosClient.get(`${WA_GATEWAY_URL}/accounts`);
    res.json(response.data);
  } catch (error) {
    console.error('Error al obtener cuentas de wa-gateway:', error);
    res.status(500).json({ error: 'Error al obtener cuentas' });
  }
});

// Proxy for GET /accounts/:id
app.get('/api/accounts/:accountId', async (req, res) => {
  try {
    const { accountId } = req.params;
    const response = await axiosClient.get(`${WA_GATEWAY_URL}/accounts/${accountId}`);
    res.json(response.data);
  } catch (error) {
    console.error('Error al obtener cuenta de wa-gateway:', error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al obtener cuenta' };
    res.status(status).json(payload);
  }
});

// Proxy for GET /accounts/:id/qr
app.get('/api/accounts/:accountId/qr', async (req, res) => {
  try {
    const { accountId } = req.params;
    const response = await axiosClient.get(`${WA_GATEWAY_URL}/accounts/${accountId}/qr`);
    res.json(response.data);
  } catch (error) {
    console.error('Error al obtener QR de wa-gateway:', error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al obtener QR' };
    res.status(status).json(payload);
  }
});

// Proxy for POST /accounts/:id/login
app.post('/api/accounts/:accountId/login', async (req, res) => {
  try {
    const { accountId } = req.params;
    const response = await axiosClient.post(
      `${WA_GATEWAY_URL}/accounts/${accountId}/login`,
      req.body
    );
    res.json(response.data);
  } catch (error) {
    console.error('Error al iniciar sesión en wa-gateway:', error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al iniciar sesión' };
    res.status(status).json(payload);
  }
});

// Proxy for POST /accounts/:id/logout
app.post('/api/accounts/:accountId/logout', async (req, res) => {
  try {
    const { accountId } = req.params;
    const response = await axiosClient.post(`${WA_GATEWAY_URL}/accounts/${accountId}/logout`);
    res.json(response.data);
  } catch (error) {
    console.error('Error al cerrar sesión en wa-gateway:', error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al cerrar sesión' };
    res.status(status).json(payload);
  }
});

// Proxy for POST /send
app.post('/api/send', async (req, res) => {
  try {
    const response = await axiosClient.post(`${WA_GATEWAY_URL}/send`, req.body);
    res.json(response.data);
  } catch (error) {
    console.error('Error al enviar mensaje via wa-gateway:', error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al enviar mensaje' };
    res.status(status).json(payload);
  }
});

// Proxy for SSE /events/stream
app.get('/api/events/stream', async (req, res) => {
  try {
    const response = await axiosClient.get(`${WA_GATEWAY_URL}/events/stream`, {
      responseType: 'stream'
    });

    // Set SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    // Pipe events to client
    response.data.pipe(res);
  } catch (error) {
    console.error('Error en SSE stream:', error);
    if (!res.headersSent) {
      res.status(500).json({ error: 'Error en stream de eventos' });
    }
  }
});

// ============================================================================
// Legacy endpoints (deprecated - redirect to wa-gateway)
// ============================================================================

// Endpoint de health check
app.get('/health', async (req, res) => {
  const healthStatus = {
    status: 'healthy',
    service: 'frontend-service',
    port: PORT,
    timestamp: new Date().toISOString(),
    dependencies: {},
  };

  const healthResults = await Promise.allSettled(
    WHATSAPP_INSTANCES.map(async instance => {
      const dep = { name: instance.name, status: 'unknown' };
      try {
        const { data } = await axiosClient.get(`${instance.url}/health`, { timeout: 3000 });
        const dependencyStatus = data.status || data.health || 'unknown';
        dep.status = dependencyStatus;
        dep.whatsapp_status = data.whatsapp_status || data.status || null;
        dep.ai_service = data.ai_service || null;
        dep.timestamp = data.timestamp || null;
        return { instance, dep };
      } catch (error) {
        dep.status = 'unreachable';
        dep.error = error.message;
        return { instance, dep };
      }
    })
  );

  for (const result of healthResults) {
    if (result.status === 'fulfilled') {
      const { instance, dep } = result.value;
      healthStatus.dependencies[instance.id] = dep;
      if (dep.status !== 'healthy') {
        healthStatus.status = dep.status === 'degraded' ? 'degraded' : 'unhealthy';
      }
    }
  }

  res.json(healthStatus);
});

// Iniciar servidor
app.listen(PORT, '0.0.0.0', () => {
  console.warn(`🚀 Frontend Service corriendo en puerto ${PORT}`);
  console.warn(`📱 Dashboard disponible en: http://localhost:${PORT}`);
  console.warn(`🔗 Conectado a ${WHATSAPP_INSTANCES.length} instancias de WhatsApp`);
});
