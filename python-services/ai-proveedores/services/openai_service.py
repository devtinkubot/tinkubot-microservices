"""
Servicio OpenAI para procesamiento de mensajes de proveedores.

Este módulo encapsula la lógica de interacción con la API de OpenAI
para generar respuestas contextualizadas para proveedores.
"""

import logging
from typing import cast

# Prompt del sistema para el asistente de proveedores
PROVIDER_SYSTEM_PROMPT = """Eres un asistente de TinkuBot Proveedores. Tu función es:

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


async def procesar_mensaje_proveedor(openai_client, message: str, phone: str) -> str:
    """
    Procesa un mensaje de proveedor usando OpenAI.

    Esta función utiliza el modelo GPT-3.5-turbo para generar respuestas
    contextualizadas a consultas de proveedores, manteniendo un tono
    profesional y amigable.

    Args:
        openai_client: Cliente de OpenAI inicializado (instancia de OpenAI)
        message: Mensaje de texto enviado por el proveedor
        phone: Número de teléfono del proveedor (para contexto/logs)

    Returns:
        str: Respuesta generada por OpenAI o mensaje de error

    Example:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="...")
        >>> response = await procesar_mensaje_proveedor(
        ...     client, "¿Cómo me registro?", "+593999999999"
        ... )
        >>> print(response)
    """
    if not openai_client:
        return "Lo siento, el servicio de IA no está disponible en este momento."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": PROVIDER_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        return cast(str, response.choices[0].message.content)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error procesando mensaje con OpenAI: {e}")
        return (
            "Lo siento, tuve un problema al procesar tu mensaje. "
            "Por favor intenta de nuevo."
        )
