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
  const { getClientStatus } = services;

  // Endpoint para obtener el estado
  app.get('/status', (req, res) => {
    const currentStatus = getClientStatus ? getClientStatus() : services.clientStatus;
    res.json({ status: currentStatus });
  });
}

module.exports = statusRoutes;
