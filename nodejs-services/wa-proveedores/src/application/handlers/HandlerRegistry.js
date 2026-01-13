/**
 * HandlerRegistry.js
 * Registro y dispatch de handlers de mensajes (Strategy Pattern)
 *
 * Responsabilidad:
 * - Registrar múltiples handlers de mensajes
 * - Dispatch dinámico según el tipo de mensaje
 * - Facilitar extensión sin modificar código existente (OCP)
 */

/**
 * Clase HandlerRegistry
 * Implementa el Strategy Pattern para dispatch de mensajes
 */
class HandlerRegistry {
  constructor() {
    this.handlers = [];
  }

  /**
   * Registra un handler en el registry
   * @param {BaseMessageHandler} handler - Handler a registrar
   */
  register(handler) {
    if (!handler || typeof handler.canHandle !== 'function' || typeof handler.handle !== 'function') {
      throw new Error('Handler must implement canHandle and handle methods');
    }
    this.handlers.push(handler);
  }

  /**
   * Despacha un mensaje al primer handler que pueda procesarlo
   * @param {object} message - Mensaje de WhatsApp
   * @returns {Promise<boolean>} true si algún handler procesó el mensaje
   */
  async dispatch(message) {
    console.warn(`[HandlerRegistry] Dispatching message type: ${message.type}, from: ${message.from}`);
    for (const handler of this.handlers) {
      try {
        const handlerName = handler.constructor.name;
        const canHandle = handler.canHandle(message);
        console.warn(`[HandlerRegistry] ${handlerName}.canHandle(${message.type}): ${canHandle}`);
        if (canHandle) {
          console.warn(`[HandlerRegistry] Delegating to ${handlerName}`);
          await handler.handle(message);
          return true;
        }
      } catch (error) {
        console.error('Error in handler:', error);
        // Continuar con el siguiente handler si hay un error
      }
    }

    // Ningún handler pudo procesar el mensaje
    console.warn('No handler found for message type:', message.type);
    return false;
  }

  /**
   * Obtiene todos los handlers registrados
   * @returns {Array<BaseMessageHandler>} Lista de handlers
   */
  getHandlers() {
    return [...this.handlers];
  }

  /**
   * Limpia todos los handlers registrados
   */
  clear() {
    this.handlers = [];
  }

  /**
   * Obtiene el número de handlers registrados
   * @returns {number} Número de handlers
   */
  get count() {
    return this.handlers.length;
  }
}

module.exports = HandlerRegistry;
