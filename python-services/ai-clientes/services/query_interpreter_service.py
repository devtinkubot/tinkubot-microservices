"""
Query Interpreter Service - Interpreta queries de usuarios usando IA.

Este módulo contiene la lógica para interpretar mensajes de usuarios
y extraer información estructurada (profesión, ciudad, detalles).

DIFERENCIADOR: Usa IA para entender la intención detrás de las palabras.
Ejemplo: "tengo goteras" → "plomero"
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from openai import AsyncOpenAI
from utils.services_utils import _safe_json_loads

# Logger del módulo
logger = logging.getLogger(__name__)


# ============================================================================
# QUERY INTERPRETER SERVICE
# ============================================================================

class QueryInterpreterService:
    """Interpreta queries de usuarios usando IA (DIFERENCIADOR).

    Responsabilidades:
    - Entender la intención del usuario ("tengo goteras" → "plomero")
    - Extraer profesión, ciudad y detalles
    - Fallback a interpretación simple sin IA
    """

    def __init__(self, openai_client: AsyncOpenAI):
        """Inicializa el servicio de interpretación de queries.

        Args:
            openai_client: Cliente OpenAI asíncrono
        """
        self.client = openai_client
        self.system_prompt = """Eres un asistente experto que interpreta necesidades de servicios en Ecuador.

El usuario te dirá lo que necesita en lenguaje natural.
Tu tarea es extraer:
1. profesion: el servicio principal (plomero, electricista, albañil, carpintero, pintor, marketing, etc)
2. ciudad: la ciudad donde lo necesita (si está explícita)
3. detalles: descripción ampliada del servicio (para enviar a proveedores)

REGLAS:
- La profesión debe ser un término de búsqueda estándar (ej: "plomero", no "fontanero")
- Mapeos específicos IMPORTANTES:
  * "gestor de redes sociales" → "marketing"
  * "community manager" → "marketing"
  * "social media manager" → "marketing"
  * "administrador de redes sociales" → "marketing"
  * "redes sociales" → "marketing"
  * "goteras" / "fugas" → "plomero"
  * "cortocircuito" / "problemas eléctricos" → "electricista"
- Si la ciudad no está clara, déjala vacía
- Los detalles deben mantener el lenguaje original del usuario

Responde SOLO en JSON formato:
{
  "profesion": "plomero",
  "ciudad": "Quito",
  "detalles": "tengo goteras en el techo de la casa"
}"""

    async def interpret_query(
        self,
        user_message: str,
        city_context: Optional[str] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
        timeout_seconds: float = 5.0
    ) -> Dict[str, Any]:
        """Interpreta query del usuario con IA.

        Args:
            user_message: Mensaje del usuario en lenguaje natural
            city_context: Ciudad conocida (opcional, del contexto de la conversación)
            semaphore: Semáforo para limitar concurrencia OpenAI
            timeout_seconds: Timeout para llamadas a OpenAI

        Returns:
            Dict con:
                - profession: profesión extraída
                - city: ciudad extraída (o city_context si no se detectó)
                - details: detalles del servicio
        """
        # Validar que no sea un número puro (sin contexto no tiene sentido)
        if user_message.strip().isdigit():
            logger.info(f"⚠️ Número puro detectado en interpret_query, rechazando: '{user_message}'")
            return {
                "profession": None,
                "city": city_context,
                "details": user_message
            }

        try:
            # Usar semáforo si está disponible
            if semaphore:
                async with semaphore:
                    response = await asyncio.wait_for(
                        self._call_openai(user_message),
                        timeout=timeout_seconds
                    )
            else:
                response = await asyncio.wait_for(
                    self._call_openai(user_message),
                    timeout=timeout_seconds
                )

            result = self._parse_openai_response(response)

            # Override ciudad si viene del contexto y IA no la detectó
            if city_context and not result.get("ciudad"):
                result["ciudad"] = city_context

            return {
                "profession": result.get("profesion", user_message),
                "city": result.get("ciudad", city_context or ""),
                "details": result.get("detalles", user_message)
            }

        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Timeout interpretando query: '{user_message[:50]}...'")
            return self._fallback_interpretation(user_message, city_context)

        except Exception as e:
            logger.error(f"❌ Error interpretando query: {e}")
            return self._fallback_interpretation(user_message, city_context)

    async def _call_openai(self, user_message: str):
        """Llama a OpenAI para interpretar el query (método privado)."""
        return await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f'Interpreta esta solicitud: "{user_message}"'}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=200
        )

    def _parse_openai_response(self, response) -> Dict:
        """Parsea respuesta de OpenAI (método privado)."""
        if not response.choices:
            raise ValueError("OpenAI respondió sin choices")

        content = (response.choices[0].message.content or "").strip()

        # Limpiar markdown si está presente
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"```$", "", content).strip()

        parsed = _safe_json_loads(content)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError(f"No se pudo parsear respuesta JSON: {content}")

        return parsed

    def _fallback_interpretation(
        self,
        message: str,
        city: Optional[str]
    ) -> Dict[str, Any]:
        """Fallback simple sin IA (método privado).

        Si IA falla, usa el mensaje tal cual como profesión.
        """
        # Si es solo un número, no tratar como profesión
        if message.strip().isdigit():
            logger.info(f"⚠️ Número puro detectado en fallback, rechazando: '{message}'")
            return {
                "profession": None,
                "city": city or "",
                "details": message
            }

        logger.info(f"🔄 Usando fallback sin IA para: '{message[:50]}...'")

        # Normalización simple: minúsculas, quitar espacios extras
        profession = message.strip().lower()

        return {
            "profession": profession,
            "city": city or "",
            "details": message
        }

    async def interpret_query_v2(
        self,
        user_message: str,
        city_context: Optional[str] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
        timeout_seconds: float = 5.0,
        expand_query: bool = True
    ) -> Dict[str, Any]:
        """
        Interpreta query V2 con expansión de términos (Enhanced Search).

        MEJORAS (Plan Mejoras Inmediatas - Enero 2026):
        - Usa QueryExpander para expandir queries con sinónimos
        - Caché en Redis para expansiones repetidas
        - Fallback a sinónimos estáticos si OpenAI falla

        ESTRATEGIA BACKWARD COMPATIBLE:
        - Si expand_query=False, usa flujo V1 original
        - Si QueryExpander no está inicializado, usa flujo V1

        Args:
            user_message: Mensaje del usuario
            city_context: Ciudad conocida del contexto
            semaphore: Semáforo para limitar concurrencia OpenAI
            timeout_seconds: Timeout para OpenAI
            expand_query: Si True, expande query con sinónimos

        Returns:
            Dict con:
                - profession: profesión interpretada
                - city: ciudad interpretada
                - details: detalles del servicio
                - expanded_terms: términos expandidos (si expand_query=True)
                - expansion_method: método usado ("cache", "ai", "static", "none")
        """
        from core.feature_flags import USE_QUERY_EXPANSION

        # Si feature flag está desactivado o expand_query=False, usar flujo V1
        if not USE_QUERY_EXPANSION or not expand_query:
            logger.debug("⚠️ USE_QUERY_EXPANSION=False o expand_query=False, usando flujo V1")
            result = await self.interpret_query(
                user_message,
                city_context,
                semaphore,
                timeout_seconds
            )
            return {
                **result,
                "expanded_terms": None,
                "expansion_method": "none"
            }

        # Flujo V2 con QueryExpander
        try:
            from services.query_expansion import get_query_expander

            expander = get_query_expander()
            if not expander:
                logger.warning("⚠️ QueryExpander no inicializado, usando flujo V1")
                result = await self.interpret_query(
                    user_message,
                    city_context,
                    semaphore,
                    timeout_seconds
                )
                return {
                    **result,
                    "expanded_terms": None,
                    "expansion_method": "none"
                }

            # Paso 1: Interpretar query con IA (flujo V1)
            interpreted = await self.interpret_query(
                user_message,
                city_context,
                semaphore,
                timeout_seconds
            )

            profession = interpreted.get("profession")
            city = interpreted.get("city")

            # Paso 2: Expandir query con sinónimos
            expansion_result = await expander.expand_query(
                query=user_message,
                profession=profession,
                use_ai=True,
                semaphore=semaphore,
                timeout_seconds=timeout_seconds
            )

            expanded_terms = expansion_result.get("expanded_terms", [])
            inferred_profession = expansion_result.get("inferred_profession")

            logger.info(
                f"✅ [V2] Query expandida: '{user_message[:30]}...' "
                f"→ {len(expanded_terms)} términos "
                f"(método: {expansion_result.get('expansion_method')})"
            )

            # Si se infirió una profesión diferente, usarla
            if inferred_profession and inferred_profession != profession:
                logger.info(f"🔮 [V2] Profesión inferida: '{profession}' → '{inferred_profession}'")
                profession = inferred_profession

            return {
                "profession": profession or user_message,
                "city": city or city_context or "",
                "details": interpreted.get("details", user_message),
                "expanded_terms": expanded_terms,
                "expansion_method": expansion_result.get("expansion_method", "unknown"),
                "inferred_profession": inferred_profession
            }

        except Exception as e:
            logger.error(f"❌ [V2] Error en interpretación con expansión: {e}")
            # Fallback a V1
            logger.info("🔄 [V2] Fallback a flujo V1 por error")
            result = await self.interpret_query(
                user_message,
                city_context,
                semaphore,
                timeout_seconds
            )
            return {
                **result,
                "expanded_terms": None,
                "expansion_method": "fallback"
            }


# ============================================================================
# INSTANCIA GLOBAL (se inicializa en main.py)
# ============================================================================

query_interpreter: Optional[QueryInterpreterService] = None


def initialize_query_interpreter(
    openai_client: Optional[AsyncOpenAI],
    cache_manager: Optional[Any] = None
) -> None:
    """Inicializa el servicio de interpretación de queries.

    Args:
        openai_client: Cliente OpenAI (opcional, si no hay se deshabilita)
        cache_manager: CacheManager opcional para QueryExpander
    """
    global query_interpreter

    if openai_client:
        query_interpreter = QueryInterpreterService(openai_client)
        logger.info("✅ QueryInterpreterService inicializado")

        # Inicializar QueryExpander también
        try:
            from services.query_expansion import initialize_query_expander
            initialize_query_expander(openai_client, cache_manager)
            logger.info("✅ QueryExpander inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando QueryExpander: {e}")
    else:
        query_interpreter = None
        logger.warning("⚠️ QueryInterpreterService deshabilitado (sin OpenAI)")
