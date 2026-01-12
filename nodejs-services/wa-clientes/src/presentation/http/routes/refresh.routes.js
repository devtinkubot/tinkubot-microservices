/**
 * refresh.routes.js
 * Endpoints para regeneración de sesión
 *
 * Responsabilidad:
 * - Manejar peticiones HTTP para regeneración de sesión
 * - Delegar lógica de negocio al servicio correspondiente
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
      // Solución 3: Permitir limpieza forzada con parámetro {force: true}
      const { force = false } = req.body || {};

      const result = await resetWhatsAppSession('manual', { attemptLogout: true, force });
      if (result === 'in_progress') {
        return res.status(409).json({
          success: false,
          error: 'Ya hay un proceso de regeneración en curso.',
        });
      }

      if (result === 'error') {
        return res.status(500).json({
          success: false,
          error: 'No se pudo regenerar el código QR. Posible sesión corrupta.',
        });
      }

      res.json({
        success: true,
        message: force
          ? 'Sesión eliminada forzadamente. Se generará nuevo QR.'
          : 'Regeneración de QR iniciada. Escanea el nuevo código cuando aparezca.',
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
