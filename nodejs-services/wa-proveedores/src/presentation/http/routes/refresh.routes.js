/**
 * refresh.routes.js
 * Endpoints para regeneración de sesión
 *
 * Responsabilidad:
 * - Regenerar QR code
 * - Reiniciar sesión de WhatsApp
 */

/**
 * Registra los endpoints de refresh
 * @param {object} app - Aplicación Express
 * @param {object} services - Servicios del sistema
 */
async function refreshRoutes(app, services) {
  const { resetWhatsAppSession, instanceName } = services;

  app.post('/refresh', async (req, res) => {
    try {
      const result = await resetWhatsAppSession('manual', { attemptLogout: true });
      if (result === 'in_progress') {
        return res.status(409).json({
          success: false,
          error: 'Ya hay un proceso de regeneración en curso.',
        });
      }

      res.json({
        success: true,
        message: 'Regeneración de QR iniciada. Escanea el nuevo código cuando aparezca.',
      });
    } catch (error) {
      console.error(`[${instanceName}] Error durante la regeneración manual:`, error);
      res.status(500).json({
        success: false,
        error: 'No se pudo regenerar el código QR.',
      });
    }
  });
}

module.exports = refreshRoutes;
