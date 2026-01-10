/**
 * SocketIOServer.js
 * Servidor WebSocket para notificaciones en tiempo real
 *
 * Responsabilidad:
 * - Configurar servidor Socket.IO
 * - Enviar notificaciones de estado de WhatsApp
 * - Notificar cambios de QR, conexión, desconexión
 */

const { Server } = require('socket.io');

/**
 * Clase SocketIOServer
 * Maneja las notificaciones WebSocket a clientes conectados
 */
class SocketIOServer {
  /**
   * @param {http.Server} httpServer - Servidor HTTP de Node.js
   */
  constructor(httpServer) {
    // Configurar Socket.IO con CORS habilitado
    this.io = new Server(httpServer, {
      cors: {
        origin: '*',
        methods: ['GET', 'POST'],
      },
    });
  }

  /**
   * Envía una notificación de estado genérica
   * @param {string} status - Estado a notificar
   * @param {object} data - Datos adicionales
   */
  notifyStatus(status, data = {}) {
    this.io.emit('status', {
      status,
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Notifica que un QR code está listo para ser escaneado
   * @param {string} qr - Código QR
   */
  notifyQR(qr) {
    this.notifyStatus('qr_ready', { qr });
  }

  /**
   * Notifica que el cliente de WhatsApp se ha conectado
   */
  notifyConnected() {
    this.notifyStatus('connected');
  }

  /**
   * Notifica que el cliente de WhatsApp se ha desconectado
   * @param {string} reason - Razón de la desconexión
   */
  notifyDisconnected(reason) {
    this.notifyStatus('disconnected', { reason });
  }

  /**
   * Notifica una falla de autenticación
   * @param {string} msg - Mensaje de error
   */
  notifyAuthFailure(msg) {
    this.notifyStatus('disconnected', {
      reason: 'auth_failure',
      message: msg
    });
  }

  /**
   * Obtiene la instancia de Socket.IO
   * @returns {Server} Instancia de Socket.IO
   */
  getIO() {
    return this.io;
  }
}

module.exports = SocketIOServer;
