"""Servicio de manejo de consentimiento."""

import json
import logging
from typing import Any, Dict, Optional


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
        phone: str,
    ) -> Dict[str, Any]:
        """Solicita consentimiento al cliente para uso de sus datos.

        Genera y retorna los mensajes necesarios para solicitar el
        consentimiento de datos del cliente.

        Args:
            phone: Teléfono del cliente (para logging)

        Returns:
            Dict con la estructura:
                {
                    "messages": [
                        {"response": "mensaje 1"},
                        {"response": "mensaje 2"}
                    ]
                }
        """
        from flows.mensajes import mensajes_consentimiento

        self.logger.info(f"🔐 Solicitando consentimiento a cliente {phone}")

        messages = [msg for msg in mensajes_consentimiento()]

        self.logger.info(f"✅ Mensajes de consentimiento generados para {phone}")

        return {"messages": messages}

    async def procesar_respuesta(
        self,
        phone: str,
        customer_profile: Dict[str, Any],
        selected: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Procesa la respuesta de consentimiento del cliente.

        Maneja tanto aceptación como rechazo del consentimiento,
        actualizando el registro del cliente y guardando el registro
        legal de consentimiento.

        Args:
            phone: Teléfono del cliente
            customer_profile: Perfil del cliente con datos de Supabase
            selected: Opción seleccionada ("1", "Acepto", etc.)
            payload: Payload completo del mensaje de WhatsApp con metadata

        Returns:
            Dict con la respuesta apropiada:
                - Si acepta: {"response": "mensaje_inicial"}
                - Si rechaza: {"response": "mensaje_rechazo"}
        """
        from templates.mensajes.consentimiento import (
            mensaje_rechazo_consentimiento,
        )
        from flows.mensajes import mensaje_inicial_solicitud

        # Mapear respuesta del botón o texto
        if selected in ["1", "Acepto"]:
            response = "accepted"

            self.logger.info(f"✅ Cliente {phone} ACEPTÓ consentimiento")

            # Actualizar has_consent a TRUE
            try:
                await self.repo_clientes.actualizar_consentimiento(
                    customer_id=customer_profile.get("id"),
                    has_consent=True,
                )

                # Guardar registro legal en tabla consents con metadata completa
                consent_data = {
                    "consent_timestamp": payload.get("timestamp"),
                    "phone": payload.get("from_number"),
                    "message_id": payload.get("message_id"),
                    "exact_response": payload.get("content"),
                    "consent_type": "provider_contact",
                    "platform": "whatsapp",
                    "message_type": payload.get("message_type"),
                    "device_type": payload.get("device_type"),
                }

                await self.repo_clientes.registrar_consentimiento(
                    user_id=customer_profile.get("id"),
                    response=response,
                    consent_data=consent_data,
                )

                self.logger.info(
                    f"✅ Consentimiento aceptado y guardado para cliente {phone}"
                )

            except Exception as exc:
                self.logger.error(
                    f"❌ Error guardando consentimiento para {phone}: {exc}"
                )

            # Después de aceptar, continuar con el flujo normal mostrando el prompt inicial
            return {"response": mensaje_inicial_solicitud()}

        else:  # "No acepto" o cualquier otra opción
            response = "declined"
            message = mensaje_rechazo_consentimiento()

            self.logger.info(f"❌ Cliente {phone} RECHAZÓ consentimiento")

            # Guardar registro legal igualmente con metadata completa
            try:
                consent_data = {
                    "consent_timestamp": payload.get("timestamp"),
                    "phone": payload.get("from_number"),
                    "message_id": payload.get("message_id"),
                    "exact_response": payload.get("content"),
                    "consent_type": "provider_contact",
                    "platform": "whatsapp",
                    "message_type": payload.get("message_type"),
                    "device_type": payload.get("device_type"),
                }

                await self.repo_clientes.registrar_consentimiento(
                    user_id=customer_profile.get("id"),
                    response=response,
                    consent_data=consent_data,
                )

                self.logger.info(
                    f"✅ Rechazo de consentimiento guardado para cliente {phone}"
                )

            except Exception as exc:
                self.logger.error(
                    f"❌ Error guardando rechazo de consentimiento para {phone}: {exc}"
                )

            return {"response": message}
