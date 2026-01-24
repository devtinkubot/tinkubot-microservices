/**
 * rateLimit.middleware.js
 * Middleware de limitación de tasa
 *
 * Responsabilidad:
 * - Limitar requests para prevenir abuso
 */

const rateLimit = require('express-rate-limit');

/**
 * Configura middleware de rate limiting
 * @param {object} app - Aplicación Express
 * @param {object} config - Configuración del servicio
 */
function configureRateLimit(app, config) {
  app.use(
    rateLimit({
      windowMs: 60 * 1000,
      max: config.rateLimitMax,
      standardHeaders: true,
      legacyHeaders: false
    })
  );
}

module.exports = configureRateLimit;
