"""
Servicio de validación de contenido y seguridad para AI Clientes.

Este módulo contiene:
- Validación de contenido con IA (OpenAI)
- Sistema de baneos y advertencias
- Detección de contenido inapropiado o sin sentido
- Gestión de estado en Redis (TTL 15 minutos)
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from shared_lib.redis_client import redis_client
from utils.services_utils import _safe_json_loads

# Logger del módulo
logger = logging.getLogger(__name__)


# ============================================================================
# SISTEMA DE BANEO Y TRACKING DE ADVERTENCIAS
# ============================================================================

async def check_if_banned(phone: str) -> bool:
    """Verifica si el usuario está baneado.

    Args:
        phone: Número de teléfono del usuario

    Returns:
        True si el usuario está baneado, False en caso contrario
    """
    try:
        ban_data = await redis_client.get(f"ban:{phone}")
        return bool(ban_data)
    except Exception as e:
        logger.warning(f"⚠️ Error verificando ban para {phone}: {e}")
        return False


async def record_warning(phone: str, offense: str) -> None:
    """Registra una advertencia en Redis (TTL 15 min).

    Args:
        phone: Número de teléfono del usuario
        offense: Descripción de la ofensa cometida
    """
    try:
        key = f"warnings:{phone}"
        existing = await redis_client.get(key) or {}
        existing = existing if isinstance(existing, dict) else {}

        existing["count"] = existing.get("count", 0) + 1
        existing["last_warning_at"] = datetime.utcnow().isoformat()
        existing["last_offense"] = offense

        await redis_client.set(key, existing, expire=900)  # 15 minutos
        logger.info(
            f"⚠️ Advertencia registrada para {phone}: {offense} "
            f"(total: {existing['count']})"
        )
    except Exception as e:
        logger.warning(f"⚠️ Error registrando warning para {phone}: {e}")


async def record_ban(phone: str, reason: str) -> None:
    """Registra un ban de 15 minutos en Redis (TTL 15 min).

    Args:
        phone: Número de teléfono del usuario
        reason: Razón del ban
    """
    try:
        ban_data = {
            "banned_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "offense_count": 2,
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }
        await redis_client.set(f"ban:{phone}", ban_data, expire=900)  # 15 minutos
        logger.info(f"🚫 Ban registrado para {phone}: {reason}")
    except Exception as e:
        logger.warning(f"⚠️ Error registrando ban para {phone}: {e}")


async def get_warning_count(phone: str) -> int:
    """Obtiene el número de advertencias activas para un teléfono.

    Args:
        phone: Número de teléfono del usuario

    Returns:
        Número de advertencias activas (0 si no hay)
    """
    try:
        data = await redis_client.get(f"warnings:{phone}")
        if data and isinstance(data, dict):
            return data.get("count", 0)
        return 0
    except Exception as e:
        logger.warning(f"⚠️ Error obteniendo warning count para {phone}: {e}")
        return 0


# ============================================================================
# VALIDACIÓN DE CONTENIDO CON IA
# ============================================================================

async def validate_content_with_ai(
    text: str,
    phone: str,
    *,
    openai_client: Optional[AsyncOpenAI],
    openai_semaphore: Optional[asyncio.Semaphore],
    timeout_seconds: float = 5.0,
    mensaje_error_input: str,
    mensaje_advertencia: str,
    mensaje_ban_template: str
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Valida el contenido usando IA para detectar contenido ilegal/inapropiado o sin sentido.

    Retorna: (should_proceed, warning_message, ban_message)

    Args:
        text: Texto del mensaje a validar
        phone: Número de teléfono del usuario
        openai_client: Cliente OpenAI
        openai_semaphore: Semáforo para limitar concurrencia
        timeout_seconds: Timeout para llamadas a OpenAI
        mensaje_error_input: Mensaje para input sin sentido
        mensaje_advertencia: Mensaje para primera ofensa
        mensaje_ban_template: Plantilla de mensaje de ban (con {hora_reinicio})

    Returns:
        Tupla (should_proceed, warning_message, ban_message)
    """
    if not openai_client:
        logger.warning("⚠️ validate_content_with_ai sin cliente OpenAI")
        return True, None, None  # Si no hay OpenAI, permitir por defecto

    logger.info(f"🔍 Validando contenido con IA: '{text[:50]}...' (phone: {phone})")

    system_prompt = """
Eres un moderador de contenido experto. Detecta si el texto contiene:

1. CONTENIDO ILEGAL O INAPROPIADO:
   - Armas, violencia, delitos
   - Drogas, sustancias ilegales
   - Servicios sexuales, prostitución, contenido pornográfico
   - Odio, discriminación, acoso

2. INPUT SIN SENTIDO O FALSO:
   - "necesito dinero" (cuando NO busca préstamos, es engañoso)
   - "dinero abeja" (sin sentido, alucinación)
   - Textos que no expresan una necesidad real de servicio

Responde SOLO con JSON:
{
  "is_valid": true/false,
  "category": "valid" | "illegal" | "inappropriate" | "nonsense" | "false",
  "reason": "explicación breve"
}
"""

    user_prompt = f'Analiza este mensaje de usuario: "{text}"'

    try:
        async with openai_semaphore:
            response = await asyncio.wait_for(
                openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=150,
                ),
                timeout=timeout_seconds,
            )

        if not response.choices:
            logger.warning("⚠️ OpenAI respondió sin choices en validate_content_with_ai")
            return True, None, None  # Permitir por defecto si falla

        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"```$", "", content).strip()

        logger.debug(f"🔍 Respuesta validación IA: {content}")

        parsed = _safe_json_loads(content)
        if not parsed or not isinstance(parsed, dict):
            logger.warning(f"⚠️ No se pudo parsear respuesta de validación: {content}")
            return True, None, None  # Permitir por defecto si falla

        is_valid = parsed.get("is_valid", True)
        category = parsed.get("category", "valid")
        reason = parsed.get("reason", "")

        # Caso 1: Contenido válido
        if is_valid and category == "valid":
            logger.info(f"✅ Contenido válido: '{text[:30]}...'")
            return True, None, None

        # Caso 2: Input sin sentido o falso (NO banea, solo rechaza)
        if category in ("nonsense", "false"):
            logger.info(f"❌ Input sin sentido detectado: '{text[:30]}...' - {reason}")
            return False, mensaje_error_input, None

        # Caso 3: Contenido ilegal/inapropiado (puede banear)
        # Verificar advertencias previas
        warning_count = await get_warning_count(phone)

        if warning_count == 0:
            # Primera ofensa: advertir
            logger.warning(f"⚠️ Primera ofensa ilegal/inapropiado para {phone}: {reason}")
            await record_warning(phone, f"{category}: {reason}")
            return False, mensaje_advertencia, None
        else:
            # Segunda ofensa: banear
            logger.warning(f"🚫 Segunda ofensa ilegal/inapropiado para {phone}: BANEANDO")
            await record_ban(phone, f"{category}: {reason} (2da ofensa)")

            # Calcular hora de reinicio
            restart_time = datetime.utcnow() + timedelta(minutes=15)
            restart_str = restart_time.strftime("%H:%M")

            ban_msg = mensaje_ban_template.format(hora_reinicio=restart_str)
            return False, None, ban_msg

    except asyncio.TimeoutError:
        logger.warning("⚠️ Timeout en validate_content_with_ai")
        return True, None, None  # Permitir por defecto si timeout
    except Exception as exc:
        logger.exception("Fallo en validate_content_with_ai: %s", exc)
        return True, None, None  # Permitir por defecto si error
