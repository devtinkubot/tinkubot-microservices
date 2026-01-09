"""
Servicio de gestión de consentimiento de clientes para AI Clientes.

Este módulo contiene:
- Validación de consentimiento de clientes
- Procesamiento de respuestas de consentimiento
- Gestión de registros legales en Supabase
- Normalización de inputs de botones/opciones
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from utils.db_utils import run_supabase
from templates.prompts import (
    mensajes_flujo_consentimiento,
    opciones_consentimiento_textos,
)
from utils.services_utils import interpret_yes_no

logger = logging.getLogger(__name__)


class ConsentService:
    """Servicio de operaciones de consentimiento de clientes."""

    def __init__(self, supabase_client):
        """
        Inicializa el servicio de consentimiento.

        Args:
            supabase_client: Cliente Supabase para operaciones de DB
        """
        self.supabase = supabase_client

    async def request_consent(self, phone: str) -> Dict[str, Any]:
        """
        Envía mensaje de solicitud de consentimiento con formato numérico.

        Args:
            phone: Número de teléfono del cliente

        Returns:
            Dict con mensajes de consentimiento formateados
        """
        messages = [{"response": msg} for msg in mensajes_flujo_consentimiento()]
        return {"messages": messages}

    async def handle_consent_response(
        self,
        phone: str,
        customer_profile: Dict[str, Any],
        selected_option: str,
        payload: Dict[str, Any],
        mensaje_inicial_servicio: str,
    ) -> Dict[str, Any]:
        """
        Maneja la respuesta de consentimiento del cliente.

        Args:
            phone: Número de teléfono del cliente
            customer_profile: Perfil del cliente desde DB
            selected_option: Opción seleccionada ("1" o "2")
            payload: Payload completo del mensaje de WhatsApp
            mensaje_inicial_servicio: Mensaje inicial a enviar tras aceptar

        Returns:
            Dict con respuesta para el cliente
        """
        # Mapear respuesta del botón o texto
        if selected_option in ["1", "Acepto"]:
            response = "accepted"

            # Actualizar has_consent a TRUE
            try:
                await run_supabase(
                    lambda: self.supabase.table("customers")
                    .update({"has_consent": True})
                    .eq("id", customer_profile.get("id"))
                    .execute(),
                    label="customers.update_consent",
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

                consent_record = {
                    "user_id": customer_profile.get("id"),
                    "user_type": "customer",
                    "response": response,
                    "message_log": json.dumps(consent_data, ensure_ascii=False),
                }
                await run_supabase(
                    lambda: self.supabase.table("consents").insert(consent_record).execute(),
                    label="consents.insert_opt_in",
                )

                logger.info(f"✅ Consentimiento aceptado por cliente {phone}")

            except Exception as exc:
                logger.error(f"❌ Error guardando consentimiento para {phone}: {exc}")

            # Después de aceptar, continuar con el flujo normal mostrando el prompt inicial
            return {"response": mensaje_inicial_servicio}

        else:  # "No acepto"
            response = "declined"
            message = """Entendido. Sin tu consentimiento no puedo compartir tus datos con proveedores.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""

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

                consent_record = {
                    "user_id": customer_profile.get("id"),
                    "user_type": "customer",
                    "response": response,
                    "message_log": json.dumps(consent_data, ensure_ascii=False),
                }
                await run_supabase(
                    lambda: self.supabase.table("consents").insert(consent_record).execute(),
                    label="consents.insert_decline",
                )

                logger.info(f"❌ Consentimiento rechazado por cliente {phone}")

            except Exception as exc:
                logger.error(
                    f"❌ Error guardando rechazo de consentimiento para {phone}: {exc}"
                )

            return {"response": message}

    def normalize_button(self, val: Optional[str]) -> Optional[str]:
        """
        Normaliza valores de botones/opciones enviados desde WhatsApp.

        - Extrae el número inicial (e.g. "1 Sí, acepto" -> "1")
        - Compacta espacios adicionales
        - Devuelve None si la cadena está vacía tras limpiar

        Args:
            val: Valor del botón/opción a normalizar

        Returns:
            Valor normalizado o None
        """
        if val is None:
            return None

        text = str(val).strip()
        if not text:
            return None

        # Reemplazar espacios múltiples por uno solo
        text = re.sub(r"\s+", " ", text)

        # Si inicia con un número (1, 2, 10, etc.), devolver solo el número
        match = re.match(r"^(\d+)", text)
        if match:
            return match.group(1)

        return text

    async def validate_and_handle_consent(
        self,
        phone: str,
        customer_profile: Dict[str, Any],
        payload: Dict[str, Any],
        mensaje_inicial_servicio: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Valida el consentimiento del cliente y maneja la respuesta si no lo tiene.

        Esta función centraliza toda la lógica de validación de consentimiento que
        antes estaba en handle_whatsapp_message().

        Args:
            phone: Número de teléfono del cliente
            customer_profile: Perfil del cliente desde DB
            payload: Payload completo del mensaje de WhatsApp
            mensaje_inicial_servicio: Mensaje inicial a enviar tras aceptar

        Returns:
            Dict con respuesta si requiere acción (solicitud o respuesta de consentimiento)
            None si el cliente ya tiene consentimiento y puede continuar
        """
        # Si no hay perfil, solicitar consentimiento
        if not customer_profile:
            return await self.request_consent(phone)

        # Si ya tiene consentimiento, permitir continuar
        if customer_profile.get("has_consent"):
            return None

        # No tiene consentimiento, verificar si está respondiendo a la solicitud
        selected = self.normalize_button(payload.get("selected_option"))
        text_content_raw = (payload.get("content") or "").strip()
        text_numeric_option = self.normalize_button(text_content_raw)

        # Normalizar para comparaciones case-insensitive
        selected_lower = selected.lower() if isinstance(selected, str) else None

        # Priorizar opciones seleccionadas mediante botones o quick replies
        if selected in {"1", "2"}:
            return await self.handle_consent_response(
                phone, customer_profile, selected, payload, mensaje_inicial_servicio
            )

        if selected_lower in {
            opciones_consentimiento_textos[0].lower(),
            opciones_consentimiento_textos[1].lower(),
        }:
            option_to_process = (
                "1" if selected_lower == opciones_consentimiento_textos[0].lower() else "2"
            )
            return await self.handle_consent_response(
                phone, customer_profile, option_to_process, payload, mensaje_inicial_servicio
            )

        # Interpretar texto libre numérico (ej. usuario responde "1" o "2")
        if text_numeric_option in {"1", "2"}:
            return await self.handle_consent_response(
                phone, customer_profile, text_numeric_option, payload, mensaje_inicial_servicio
            )

        # Interpretar textos afirmativos/negativos libres
        is_consent_text = interpret_yes_no(text_content_raw) == True
        is_declined_text = interpret_yes_no(text_content_raw) == False

        if is_consent_text:
            return await self.handle_consent_response(
                phone, customer_profile, "1", payload, mensaje_inicial_servicio
            )

        if is_declined_text:
            return await self.handle_consent_response(
                phone, customer_profile, "2", payload, mensaje_inicial_servicio
            )

        # No entendió la respuesta, volver a solicitar consentimiento
        return await self.request_consent(phone)
