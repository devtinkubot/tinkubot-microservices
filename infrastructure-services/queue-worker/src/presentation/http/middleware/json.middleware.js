/**
 * json.middleware.js
 * Middleware JSON parser
 *
 * Responsabilidad:
 * - Parsear body de requests JSON
 */

const express = require('express');

/**
 * Configura middleware JSON parser
 * @param {object} app - Aplicación Express
 * @param {object} config - Configuración del servicio
 */
function configureJsonParser(app, config) {
  app.use(
    express.json({
      limit: config.bodySizeLimit
    })
  );
}

module.exports = configureJsonParser;
