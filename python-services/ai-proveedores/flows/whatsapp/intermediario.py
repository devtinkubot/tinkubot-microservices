"""
Intermediario de OpenAI para procesamiento de mensajes de WhatsApp.

Este módulo contiene la función para procesar mensajes entrantes
con OpenAI antes de enviarlos al usuario.
"""

import logging
import sys
from pathlib import Path
from typing import cast

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logger = logging.getLogger(__name__)


async def procesar_con_openai(message: str, phone: str) -> str:
    """
    Procesar mensaje entrante con OpenAI.

    Args:
        message: Contenido del mensaje a procesar
        phone: Número de teléfono del remitente

    Returns:
        Respuesta generada por OpenAI o mensaje de error
    """
    from main import openai_client  # Import dinámico para evitar circular import

    if not openai_client:
        return "Lo siento, el servicio de IA no está disponible en este momento."

    try:
        # Contexto para el asistente de proveedores
        system_prompt = """Eres un asistente de TinkuBot Proveedores. Tu función es:

1. Ayudar a los proveedores a registrarse en el sistema
2. Responder preguntas sobre cómo funciona el servicio
3. Proporcionar información sobre servicios disponibles
4. Ser amable y profesional

Si un proveedor quiere registrarse, pregunta:
- Nombre completo
- Profesión oficio
- Número de teléfono
- Correo electrónico (opcional)
- Dirección
- Ciudad

Si es una consulta general, responde amablemente."""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        return cast(str, response.choices[0].message.content)
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje con OpenAI: {e}")
        return (
            "Lo siento, tuve un problema al procesar tu mensaje. "
            "Por favor intenta de nuevo."
        )
