/**
 * status.routes.js
 * Endpoints para consulta de estado
 *
 * Responsabilidad:
 * - Proporcionar estado del cliente WhatsApp
 * - Consultar estado de conexión
 */

/**
 * Registra los endpoints de estado
 * @param {object} app - Aplicación Express
 * @param {object} services - Servicios del sistema
 */
async function statusRoutes(app, services) {
  const { clientStatus } = services;

  // Endpoint para obtener el estado
  app.get('/status', (req, res) => {
    res.json({ status: clientStatus });
  });
}

module.exports = statusRoutes;
