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
  const { getClientStatus, getQrCodeData } = services;

  // Endpoint para obtener el QR code
  app.get('/qr', (req, res) => {
    console.warn(`[QR Endpoint] getClientStatus exists: ${!!getClientStatus}`);
    console.warn(`[QR Endpoint] getQrCodeData exists: ${!!getQrCodeData}`);
    console.warn(`[QR Endpoint] services.clientStatus: ${services.clientStatus}`);
    console.warn(`[QR Endpoint] services.qrCodeData: ${services.qrCodeData}`);

    const currentStatus = getClientStatus ? getClientStatus() : services.clientStatus;
    const currentQrData = getQrCodeData ? getQrCodeData() : services.qrCodeData;

    console.warn(`[QR Endpoint] currentStatus: ${currentStatus}`);
    console.warn(`[QR Endpoint] QR data exists: ${!!currentQrData}`);

    if (currentStatus === 'qr_ready' && currentQrData) {
      res.json({ qr: currentQrData });
    } else {
      res.status(404).json({ error: 'QR code no disponible o ya conectado.' });
    }
  });
}

module.exports = qrRoutes;
