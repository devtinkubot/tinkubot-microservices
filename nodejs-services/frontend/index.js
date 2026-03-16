const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const http = require('http');
const https = require('https');
const adminProvidersRouter = require('./routes/adminProviders');
const session = require('express-session');
const app = express();

// IMPORTANT: Set trust proxy IMMEDIATELY after creating app, before any middleware
// Use 1 instead of true to avoid rate limiter bypass warning
app.set('trust proxy', 1);

const ADMIN_USER = process.env.ADMIN_USER || 'hvillalba';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const NODE_ENV = process.env.NODE_ENV || 'development';

// Security: Require ADMIN_PASSWORD in production
if (NODE_ENV === 'production' && !ADMIN_PASSWORD) {
  console.error('🚨 ERROR DE SEGURIDAD: ADMIN_PASSWORD es obligatorio en producción.');
  console.error('   Configure la variable de entorno ADMIN_PASSWORD antes de iniciar.');
  process.exit(1);
}

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
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS || '8000', 10);
const STATIC_MAX_AGE_SECONDS = parseInt(process.env.STATIC_MAX_AGE_SECONDS || '86400', 10);

const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 20 });
const httpsAgent = new https.Agent({ keepAlive: true, maxSockets: 20 });
const axiosClient = axios.create({
  httpAgent,
  httpsAgent,
  timeout: 5000
});

// WA-Gateway configuration
const WA_GATEWAY_URL = process.env.WA_GATEWAY_URL || 'http://wa-gateway:7000';

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
  console.warn('⚠️ MODO DESARROLLO: ADMIN_PASSWORD no configurado; panel sin autenticación.');
  console.warn('   Esto es aceptable solo en desarrollo. En producción, configure ADMIN_PASSWORD.');
}

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
    legacyHeaders: false,
    skip: (req) => {
      // Skip rate limit for health checks
      return req.path === '/health' || req.path === '/api/health';
    }
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
  const publicPaths = ['/health', '/login', '/api/login', '/api/logout', '/api/auth/status'];
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
      maxAge: 0,
      etag: true,
      setHeaders: (res, filePath) => {
        const isDashboardHtml = filePath.endsWith(`${path.sep}index.html`);
        res.setHeader(
          'Cache-Control',
          isDashboardHtml ? 'no-store' : 'no-store, max-age=0, must-revalidate'
        );
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
    whatsapp_gateway_url: WA_GATEWAY_URL,
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
    res.setHeader('Cache-Control', 'no-store');
    return res.sendFile(path.join(dashboardDistPath, 'index.html'));
  }
  return res.sendFile(path.join(publicPath, 'admin-dashboard.html'));
});

app.get('/admin-dashboard', (req, res) => {
  if (existeCompilacionDashboard()) {
    res.setHeader('Cache-Control', 'no-store');
    return res.sendFile(path.join(dashboardDistPath, 'index.html'));
  }
  res.setHeader('Cache-Control', 'no-store');
  return res.sendFile(path.join(publicPath, 'admin-dashboard.html'));
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

// Iniciar servidor
app.listen(PORT, '0.0.0.0', () => {
  console.warn(`🚀 Frontend Service corriendo en puerto ${PORT}`);
  console.warn(`📱 Dashboard disponible en: http://localhost:${PORT}`);
  console.warn(`🔗 Proxy saliente conectado a wa-gateway: ${WA_GATEWAY_URL}`);
});
