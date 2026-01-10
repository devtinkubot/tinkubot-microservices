/**
 * qr.routes.js
 * Endpoints para gestión de QR code
 *
 * Responsabilidad:
 * - Obtener QR code disponible
 * - Gestionar estado de autenticación
 */

/**
 * Registra los endpoints de QR
 * @param {object} app - Aplicación Express
 * @param {object} services - Servicios del sistema
 */
async function qrRoutes(app, services) {
  const { qrCodeData, clientStatus } = services;

  // Endpoint para obtener el QR code
  app.get('/qr', (req, res) => {
    if (clientStatus === 'qr_ready' && qrCodeData) {
      res.json({ qr: qrCodeData });
    } else {
      res.status(404).json({ error: 'QR code no disponible o ya conectado.' });
    }
  });
}

module.exports = qrRoutes;
