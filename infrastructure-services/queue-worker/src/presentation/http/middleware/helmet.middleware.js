/**
 * helmet.middleware.js
 * Middleware Helmet (seguridad HTTP)
 *
 * Responsabilidad:
 * - Configurar headers de seguridad
 */

const helmet = require('helmet');

/**
 * Configura middleware Helmet
 * @param {object} app - Aplicación Express
 */
function configureHelmet(app) {
  app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
}

module.exports = configureHelmet;
