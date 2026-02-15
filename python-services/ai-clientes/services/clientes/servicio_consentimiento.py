"""Servicio de manejo de consentimiento."""

import logging
from typing import Any, Dict


class ServicioConsentimiento:
    """Servicio de dominio para manejo de consentimiento de clientes.

    Gestiona el flujo de solicitud y procesamiento de consentimiento
    de datos de contacto de clientes para compartir con proveedores.
    """

    def __init__(
        self,
        repositorio_clientes,
        logger: logging.Logger,
    ):
        """Inicializa el servicio de consentimiento.

        Args:
            repositorio_clientes: Repositorio para gestionar datos de clientes y consentimientos
            logger: Logger para registro de eventos
        """
        self.repo_clientes = repositorio_clientes
        self.logger = logger

    async def solicitar_consentimiento(
        self,
        telefono: str,
    ) -> Dict[str, Any]:
        """Solicita consentimiento al cliente para uso de sus datos.

        Genera y retorna los mensajes necesarios para solicitar el
        consentimiento de datos del cliente.

        Args:
            telefono: Teléfono del cliente (para logging)

        Returns:
            Dict con la estructura:
                {
                    "messages": [
                        {"response": "mensaje 1"},
                        {"response": "mensaje 2"}
                    ]
                }
        """
        from templates.mensajes.consentimiento import mensajes_flujo_consentimiento

        self.logger.info(f"🔐 Solicitando consentimiento a cliente {telefono}")

        mensajes = [{"response": msg} for msg in mensajes_flujo_consentimiento()]

        self.logger.info(f"✅ Mensajes de consentimiento generados para {telefono}")

        return {"messages": mensajes}

    async def procesar_respuesta(
        self,
        telefono: str,
        perfil_cliente: Dict[str, Any],
        seleccionado: str,
        carga: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Procesa la respuesta de consentimiento del cliente.

        Maneja tanto aceptación como rechazo del consentimiento,
        actualizando el registro del cliente y guardando el registro
        legal de consentimiento.

        Args:
            telefono: Teléfono del cliente
            perfil_cliente: Perfil del cliente con datos de Supabase
            seleccionado: Opción seleccionada ("1", "Acepto", etc.)
            carga: Payload completo del mensaje de WhatsApp con metadata

        Returns:
            Dict con la respuesta apropiada:
                - Si acepta: {"response": "mensaje_inicial"}
                - Si rechaza: {"response": "mensaje_rechazo"}
        """
        from templates.mensajes.consentimiento import (
            mensaje_rechazo_consentimiento,
        )
        from templates.mensajes.validacion import mensaje_inicial_solicitud_servicio

        # Mapear respuesta del botón o texto
        if seleccionado in ["1", "Acepto"]:
            respuesta = "accepted"

            self.logger.info(f"✅ Cliente {telefono} ACEPTÓ consentimiento")

            # Actualizar has_consent a TRUE
            try:
                await self.repo_clientes.actualizar_consentimiento(
                    cliente_id=perfil_cliente.get("id"),
                    tiene_consentimiento=True,
                )

                # Guardar registro legal en tabla consents con metadata completa
                datos_consentimiento = {
                    "consent_timestamp": carga.get("timestamp"),
                    "phone": carga.get("from_number"),
                    "message_id": carga.get("message_id"),
                    "exact_response": carga.get("content"),
                    "consent_type": "provider_contact",
                    "platform": "whatsapp",
                    "message_type": carga.get("message_type"),
                    "device_type": carga.get("device_type"),
                }

                await self.repo_clientes.registrar_consentimiento(
                    usuario_id=perfil_cliente.get("id"),
                    respuesta=respuesta,
                    datos_consentimiento=datos_consentimiento,
                )

                self.logger.info(
                    f"✅ Consentimiento aceptado y guardado para cliente {telefono}"
                )

            except Exception as exc:
                self.logger.error(
                    f"❌ Error guardando consentimiento para {telefono}: {exc}"
                )

            # Después de aceptar, continuar con el flujo normal mostrando el prompt inicial
            return {"response": mensaje_inicial_solicitud_servicio, "consent_status": "accepted"}

        else:  # "No acepto" o cualquier otra opción
            respuesta = "declined"
            mensaje = mensaje_rechazo_consentimiento()

            self.logger.info(f"❌ Cliente {telefono} RECHAZÓ consentimiento")

            # Guardar registro legal igualmente con metadata completa
            try:
                datos_consentimiento = {
                    "consent_timestamp": carga.get("timestamp"),
                    "phone": carga.get("from_number"),
                    "message_id": carga.get("message_id"),
                    "exact_response": carga.get("content"),
                    "consent_type": "provider_contact",
                    "platform": "whatsapp",
                    "message_type": carga.get("message_type"),
                    "device_type": carga.get("device_type"),
                }

                await self.repo_clientes.registrar_consentimiento(
                    usuario_id=perfil_cliente.get("id"),
                    respuesta=respuesta,
                    datos_consentimiento=datos_consentimiento,
                )

                self.logger.info(
                    f"✅ Rechazo de consentimiento guardado para cliente {telefono}"
                )

            except Exception as exc:
                self.logger.error(
                    f"❌ Error guardando rechazo de consentimiento para {telefono}: {exc}"
                )

            return {"response": mensaje, "consent_status": "declined"}
