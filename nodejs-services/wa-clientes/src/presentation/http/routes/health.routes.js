/**
 * health.routes.js
 * Endpoints de health check
 *
 * Responsabilidad:
 * - Proporcionar endpoint de health check básico
 * - Proporcionar endpoint extendido con estado de servicios dependientes
 */

/**
 * Registra los endpoints de health check
 * @param {object} app - Aplicación Express
 * @param {object} services - Servicios del sistema (config, clientStatus, aiServiceClient, etc.)
 */
async function healthRoutes(app, services) {
  const { config, clientStatus, aiServiceClient, port, instanceId, instanceName } = services;

  // Endpoint básico de health check para orquestadores
  app.get('/health', async (req, res) => {
    const healthStatus = {
      status: 'healthy',
      instance: instanceId,
      name: instanceName,
      port,
      whatsapp_status: clientStatus,
      ai_service: 'unknown',
      websocket_connected: true,
      timestamp: new Date().toISOString(),
    };

    // Verificar conexión con AI Service Clientes
    try {
      const isHealthy = await aiServiceClient.healthCheck();
      healthStatus.ai_service = isHealthy ? 'connected' : 'disconnected';
      healthStatus.ai_service_status = isHealthy ? 'ok' : 'error';
    } catch (error) {
      healthStatus.ai_service = 'disconnected';
      healthStatus.ai_service_error = error.message;
    }

    // Si WhatsApp no está conectado, marcar como degradado
    if (clientStatus !== 'connected') {
      healthStatus.status = 'degraded';
    }

    // Si AI Service no está conectado, marcar como unhealthy
    if (healthStatus.ai_service === 'disconnected') {
      healthStatus.status = 'unhealthy';
    }

    res.json(healthStatus);
  });
}

module.exports = healthRoutes;
