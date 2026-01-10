/**
 * compression.middleware.js
 * Middleware de compresión
 *
 * Responsabilidad:
 * - Comprimir respuestas HTTP
 */

const compression = require('compression');

/**
 * Configura middleware de compresión
 * @param {object} app - Aplicación Express
 */
function configureCompression(app) {
  app.use(compression());
}

module.exports = configureCompression;
