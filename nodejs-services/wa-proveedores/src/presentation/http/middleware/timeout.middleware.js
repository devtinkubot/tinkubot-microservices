/**
 * timeout.middleware.js
 * Middleware de timeout para requests
 *
 * Responsabilidad:
 * - Establecer timeout para requests HTTP
 */

/**
 * Configura middleware de timeout
 * @param {object} app - Aplicación Express
 * @param {number} timeoutMs - Timeout en milisegundos
 */
function configureTimeout(app, timeoutMs) {
  app.use((req, res, next) => {
    res.setTimeout(timeoutMs, () => {
      if (!res.headersSent) {
        res.status(503).json({ error: 'Request timed out' });
      }
    });
    next();
  });
}

module.exports = configureTimeout;
