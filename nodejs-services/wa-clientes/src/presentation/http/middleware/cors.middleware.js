/**
 * cors.middleware.js
 * Middleware CORS
 *
 * Responsabilidad:
 * - Configurar CORS para la API
 */

const cors = require('cors');

/**
 * Configura middleware CORS
 * @param {object} app - Aplicación Express
 */
function configureCors(app) {
  app.use(cors());
}

module.exports = configureCors;
