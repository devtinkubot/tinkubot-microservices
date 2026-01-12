/**
 * send.routes.js
 * Endpoint para envío de mensajes salientes
 *
 * Responsabilidad:
 * - Validar parámetros de entrada
 * - Enviar mensajes de WhatsApp
 */

/**
 * Registra el endpoint de envío de mensajes
 * @param {object} app - Aplicación Express
 * @param {object} services - Servicios del sistema
 */
async function sendRoutes(app, services) {
  const { messageSender } = services;

  // Endpoint simple para envíos salientes desde otros servicios
  app.post('/send', async (req, res) => {
    try {
      const { to, message } = req.body || {};
      if (!to || !message) {
        return res.status(400).json({ error: 'to and message are required' });
      }
      if (typeof to !== 'string' || typeof message !== 'string') {
        return res.status(400).json({ error: 'invalid parameters' });
      }
      if (message.length > 1000) {
        return res.status(413).json({ error: 'message too long' });
      }
      await messageSender.sendText(to, message);
      return res.json({ status: 'sent' });
    } catch (err) {
      console.error('Error en /send:', err.message || err);
      return res.status(500).json({ error: 'failed to send message' });
    }
  });
}

module.exports = sendRoutes;
