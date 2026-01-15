"""
Query Expansion Service para ai-clientes.

Este módulo expande queries de búsqueda con sinónimos para mejorar
la tasa de coincidencias y reducir falsos negativos.

Estrategias de expansión:
1. Catálogo dinámico (service_synonyms en Supabase)
2. Expansión con OpenAI (sinónimos regionales EC)
3. Sinónimos estáticos de backup (fallback rápido)

Caché: Redis con TTL 3600s (1 hora)
Expected cache hit rate: 70%

Author: Claude Sonnet 4.5
Created: 2026-01-15
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Expande queries de búsqueda con sinónimos y términos relacionados.

    Estrategias de expansión (en orden de prioridad):
    1. Redis Cache (si ya se expandió antes)
    2. Catálogo dinámico (service_synonyms de Supabase)
    3. Expansión con OpenAI (IA, sinónimos regionales)
    4. Sinónimos estáticos (fallback rápido)

    Attributes:
        openai_client: Cliente OpenAI para expansión con IA
        cache_manager: CacheManager para Redis cache
        static_synonyms: Diccionario de sinónimos estáticos

    Example:
        >>> expander = QueryExpander(openai_client, cache_manager)
        >>> result = await expander.expand_query("tengo goteras")
        >>> print(result["expanded_terms"])
        ['plomero', 'plomeria', 'fugas', 'agua', 'fontaneria']
    """

    # Sinónimos estáticos de backup (cuando OpenAI falla)
    STATIC_SYNONYMS: Dict[str, List[str]] = {
        "plomero": ["plomeria", "fontanero", "gasfitero", "tuberías", "fugas", "agua"],
        "electricista": ["electricidad", "eléctrico", "cableado", "instalación eléctrica"],
        "pintor": ["pintura", "paredes", "muros", "techumbre"],
        "estilista": ["cabello", "pelo", "corte", "tinte", "mechas", "peluquería"],
        "esteticista": ["belleza", "facial", "cosmetología", "skin care", "skincare"],
        "limpieza": ["limpiar", "aseo", "aseadora"],
        "jardinero": ["jardín", "césped", "pasto", "podar", "paisajismo"],
        "veterinario": ["mascotas", "perro", "gato", "clínica veterinaria"],
        "mudanza": ["mudar", "transporte", "flete", "carga"],
        "carpintero": ["carpintería", "madera", "muebles", "armarios", "closets"],
        "cerrajero": ["cerradura", "llave", "puerta"],
        "técnico de computadoras": ["computadora", "pc", "laptop", "informática", "virus"],
        "fotógrafo": ["foto", "fotografía", "retrato", "evento"],
        "músico": ["música", "guitarra", "piano", "banda", "orquesta"],
        "cocinero": ["cocina", "chef", "comida", "restaurante"],
        "constructor": ["construcción", "albañil", "obras", "casa"],
        "masajista": ["masaje", "masajes", "masoterapia"],
    }

    # Prompt para expansión con OpenAI
    EXPANSION_PROMPT = """Eres un experto en servicios profesionales en Ecuador.

Expande esta consulta de búsqueda incluyendo sinónimos y términos relacionados.

REGLAS:
- Incluye sinónimos regionales de Ecuador
- Convierte problemas a la profesión que los resuelve
- Responde ÚNICAMENTE con un JSON válido

Ejemplos:
- "tengo goteras" → {{"expanded_terms": "plomero plomeria fugas agua fontaneria tuberías", "inferred_profession": "plomero"}}
- "limpieza facial" → {{"expanded_terms": "estética facial cosmetología cuidado piel beautician spa", "inferred_profession": "esteticista"}}
- "necesito un electricista" → {{"expanded_terms": "electricista electricidad instalacion cableado", "inferred_profession": "electricista"}}

Expande esta consulta: {user_message}

Responde en formato JSON:
{{"expanded_terms": "termino1 termino2 termino3 ...", "inferred_profession": "profesión"}}"""

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        cache_manager: Optional[Any] = None
    ):
        """Inicializa el expansor de queries.

        Args:
            openai_client: Cliente OpenAI asíncrono
            cache_manager: CacheManager opcional para Redis cache
        """
        self.client = openai_client
        self.cache_manager = cache_manager
        logger.debug("QueryExpander inicializado")

    async def expand_query(
        self,
        query: str,
        profession: Optional[str] = None,
        use_ai: bool = True,
        semaphore: Optional[Any] = None,
        timeout_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """
        Expande una query con sinónimos y términos relacionados.

        Args:
            query: Query original del usuario
            profession: Profesión conocida (opcional, acelera expansión)
            use_ai: Si es True, usa OpenAI para expansión
            semaphore: Semáforo para limitar concurrencia OpenAI
            timeout_seconds: Timeout para llamadas a OpenAI

        Returns:
            Dict con:
                - expanded_terms: List[str] de términos expandidos
                - inferred_profession: Profesión inferida (si aplica)
                - expansion_method: "cache", "dynamic", "ai", o "static"

        Example:
            >>> result = await expander.expand_query("tengo goteras")
            >>> print(result)
            {
                "expanded_terms": ["plomero", "plomeria", "fugas", "agua"],
                "inferred_profession": "plomero",
                "expansion_method": "ai"
            }
        """
        # Paso 1: Verificar caché Redis
        cache_key = self._generate_cache_key(query, profession)
        if self.cache_manager:
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.debug(f"✅ Cache HIT para query: '{query}'")
                return {
                    **cached,
                    "expansion_method": "cache"
                }

        # Paso 2: Intentar expansión con catálogo dinámico
        dynamic_result = await self._expand_with_dynamic_catalog(query, profession)
        if dynamic_result:
            logger.debug(f"✅ Expansión con catálogo dinámico para: '{query}'")
            # Guardar en caché
            await self._save_to_cache(cache_key, dynamic_result)
            return {
                **dynamic_result,
                "expansion_method": "dynamic"
            }

        # Paso 3: Expansión con OpenAI (si está habilitado)
        if use_ai:
            try:
                ai_result = await self._expand_with_openai(
                    query,
                    semaphore=semaphore,
                    timeout_seconds=timeout_seconds
                )
                if ai_result:
                    logger.debug(f"✅ Expansión con OpenAI para: '{query}'")
                    # Guardar en caché
                    await self._save_to_cache(cache_key, ai_result)
                    return {
                        **ai_result,
                        "expansion_method": "ai"
                    }
            except Exception as e:
                logger.warning(f"⚠️ Error en expansión OpenAI: {e}, usando fallback")

        # Paso 4: Fallback a sinónimos estáticos
        static_result = self._expand_with_static_synonyms(query, profession)
        logger.debug(f"✅ Expansión con sinónimos estáticos para: '{query}'")
        # Guardar en caché
        await self._save_to_cache(cache_key, static_result)
        return {
            **static_result,
            "expansion_method": "static"
        }

    def _generate_cache_key(self, query: str, profession: Optional[str]) -> str:
        """Genera clave de caché para la query."""
        key_data = f"{query}:{profession or ''}"
        return f"query_expansion:{hashlib.md5(key_data.encode()).hexdigest()}"

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene expansión desde caché Redis."""
        if not self.cache_manager:
            return None

        try:
            from core.cache import CacheNamespace

            cached = await self.cache_manager.get(
                CacheNamespace.SEARCH_RESULTS,
                cache_key
            )

            if cached:
                return json.loads(cached) if isinstance(cached, str) else cached
        except Exception as e:
            logger.warning(f"⚠️ Error leyendo caché: {e}")

        return None

    async def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Guarda expansión en caché Redis."""
        if not self.cache_manager:
            return

        try:
            from core.cache import CacheNamespace

            await self.cache_manager.set(
                CacheNamespace.SEARCH_RESULTS,
                cache_key,
                data,
                ttl=3600  # 1 hora
            )
            logger.debug(f"💾 Guardado en caché: {cache_key}")
        except Exception as e:
            logger.warning(f"⚠️ Error guardando en caché: {e}")

    async def _expand_with_dynamic_catalog(
        self,
        query: str,
        profession: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Expande query usando catálogo dinámico de sinónimos."""
        try:
            from services.dynamic_service_catalog import dynamic_service_catalog

            # Buscar sinónimos para la profesión
            canonical = await dynamic_service_catalog.find_profession(query)

            if canonical:
                # Obtener sinónimos del catálogo (retorna Dict[str, Set[str]])
                all_synonyms = await dynamic_service_catalog.get_synonyms()

                if all_synonyms and canonical in all_synonyms:
                    synonym_set = all_synonyms[canonical]
                    # Convertir Set[str] a List[str]
                    synonyms_list = list(synonym_set)

                    if synonyms_list:
                        return {
                            "expanded_terms": [canonical] + synonyms_list,
                            "inferred_profession": canonical
                        }

            return None
        except Exception as e:
            logger.debug(f"Catálogo dinámico no disponible: {e}")
            return None

    async def _expand_with_openai(
        self,
        query: str,
        semaphore: Optional[Any] = None,
        timeout_seconds: float = 3.0
    ) -> Optional[Dict[str, Any]]:
        """Expande query usando OpenAI."""
        try:
            # Aplicar semáforo si existe
            if semaphore:
                await semaphore.acquire()

            try:
                response = await self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Eres un experto en servicios en Ecuador."},
                        {"role": "user", "content": self.EXPANSION_PROMPT.format(user_message=query)}
                    ],
                    temperature=0.3,
                    max_tokens=100,
                    timeout=timeout_seconds
                )

                content = response.choices[0].message.content.strip()

                # Parsear JSON de respuesta
                result = json.loads(content)

                # Convertir expanded_terms de string a lista
                if isinstance(result.get("expanded_terms"), str):
                    result["expanded_terms"] = result["expanded_terms"].split()

                return result

            finally:
                if semaphore:
                    semaphore.release()

        except Exception as e:
            logger.warning(f"⚠️ Error en expansión OpenAI: {e}")
            return None

    def _expand_with_static_synonyms(
        self,
        query: str,
        profession: Optional[str]
    ) -> Dict[str, Any]:
        """Expande query usando sinónimos estáticos (fallback)."""
        query_lower = query.lower()

        # Buscar profesión en sinónimos estáticos
        for canonical_profession, synonyms in self.STATIC_SYNONYMS.items():
            # Verificar si la query menciona esta profesión o sinónimos
            if canonical_profession in query_lower:
                return {
                    "expanded_terms": [canonical_profession] + synonyms,
                    "inferred_profession": canonical_profession
                }

            # Verificar sinónimos
            for synonym in synonyms:
                if synonym in query_lower:
                    return {
                        "expanded_terms": [canonical_profession] + synonyms,
                        "inferred_profession": canonical_profession
                    }

        # Si no se encontró, retornar la query original tokenizada
        tokens = query_lower.split()
        return {
            "expanded_terms": tokens,
            "inferred_profession": profession or (tokens[0] if tokens else None)
        }


# Instancia global (singleton)
_query_expander: Optional[QueryExpander] = None


def get_query_expander() -> Optional[QueryExpander]:
    """
    Retorna la instancia global del QueryExpander (singleton).

    Returns:
        QueryExpander: Instancia del expansor

    Example:
        >>> from services.query_expansion import get_query_expander
        >>> expander = get_query_expander()
        >>> result = await expander.expand_query("tengo goteras")
    """
    global _query_expander
    return _query_expander


def initialize_query_expander(
    openai_client: AsyncOpenAI,
    cache_manager: Optional[Any] = None
) -> QueryExpander:
    """
    Inicializa el QueryExpander global.

    Args:
        openai_client: Cliente OpenAI
        cache_manager: CacheManager opcional

    Returns:
        QueryExpander: Instancia inicializada
    """
    global _query_expander
    _query_expander = QueryExpander(openai_client, cache_manager)
    logger.info("✅ QueryExpander singleton inicializado")
    return _query_expander
