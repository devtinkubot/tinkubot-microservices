/**
 * app.js
 * Configuración de Express
 *
 * Responsabilidad:
 * - Crear y configurar aplicación Express
 * - Registrar middleware
 * - Registrar rutas
 */

const express = require('express');

// Middleware
const configureCors = require('../middleware/cors.middleware');
const configureHelmet = require('../middleware/helmet.middleware');
const configureCompression = require('../middleware/compression.middleware');
const configureRateLimit = require('../middleware/rateLimit.middleware');
const configureJsonParser = require('../middleware/json.middleware');
const configureTimeout = require('../middleware/timeout.middleware');

// Routes
const healthRoutes = require('../routes/health.routes');
const qrRoutes = require('../routes/qr.routes');
const statusRoutes = require('../routes/status.routes');
const refreshRoutes = require('../routes/refresh.routes');
const sendRoutes = require('../routes/send.routes');

/**
 * Crea y configura la aplicación Express
 * @param {object} services - Servicios del sistema
 * @returns {object} Aplicación Express configurada
 */
function createApp(services) {
  const { config } = services;
  const REQUEST_TIMEOUT_MS = config.requestTimeoutMs;

  const app = express();

  // Middleware
  configureCors(app);
  configureHelmet(app);
  configureCompression(app);
  configureRateLimit(app, config);
  configureJsonParser(app, config);
  configureTimeout(app, REQUEST_TIMEOUT_MS);

  // Routes
  healthRoutes(app, services);
  qrRoutes(app, services);
  statusRoutes(app, services);
  refreshRoutes(app, services);
  sendRoutes(app, services);

  return app;
}

module.exports = createApp;
