"""
Servicio de mensajería para AI Clientes.
"""

import logging
import os
from typing import Any, Dict

import httpx

from shared_lib.config import settings

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
_default_whatsapp_clientes_url = f"http://wa-clientes:{settings.whatsapp_clientes_port}"
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _default_whatsapp_clientes_url,
)


class MessagingService:
    """Servicio de mensajería WhatsApp."""

    def __init__(self, supabase_client):
        """
        Inicializa el servicio de mensajería.

        Args:
            supabase_client: Cliente Supabase para operaciones de DB
        """
        self.supabase = supabase_client

    async def send_whatsapp_text(self, phone: str, text: str) -> bool:
        """
        Envía mensaje de texto vía WhatsApp.

        Args:
            phone: Número de teléfono destinatario
            text: Contenido del mensaje

        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        try:
            url = f"{WHATSAPP_CLIENTES_URL}/send"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"to": phone, "message": text})

            if resp.status_code == 200:
                logger.info(f"✅ Mensaje enviado a {phone}")
                return True

            logger.warning(
                f"WhatsApp send falló status={resp.status_code} body={resp.text[:200]}"
            )
            return False

        except Exception as e:
            logger.error(f"❌ Error enviando WhatsApp: {e}")
            return False
