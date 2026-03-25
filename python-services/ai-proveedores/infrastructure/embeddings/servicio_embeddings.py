"""
Servicio de generación de embeddings con OpenAI.

Este servicio proporciona funcionalidad para generar embeddings de texto
utilizando el modelo text-embedding-3-small de OpenAI. Incluye caché en Redis
para evitar llamadas duplicadas y reducir costos.

Características principales:
- Generación de embeddings individuales o por lotes
- Caché en Redis con TTL configurable
- Manejo de errores con reintentos
- Timeout configurable para llamadas a OpenAI
- Logging completo de operaciones
"""

import hashlib
import json
import logging
from typing import List, Optional

from openai import AsyncOpenAI

from ..redis.cliente_redis import get_redis_client

logger = logging.getLogger(__name__)


class ServicioEmbeddings:
    """
    Servicio para generar embeddings con OpenAI.

    Este servicio encapsula la lógica de generación de embeddings utilizando
    la API de OpenAI, con optimizaciones como caché en Redis para reducir
    costos y mejorar performance.

    Atributos:
        client: Cliente asíncrono de OpenAI
        model: Modelo de embeddings a usar (default: text-embedding-3-small)
        cache_ttl: Tiempo de vida del caché en segundos (default: 3600)
        timeout: Timeout en segundos para llamadas a OpenAI (default: 5)

    Ejemplo:
        >>> from openai import AsyncOpenAI
        >>> cliente = AsyncOpenAI(api_key="...")
        >>> servicio = ServicioEmbeddings(cliente)
        >>> embedding = await servicio.generar_embedding("plomería")
        >>> print(len(embedding))  # 1536
    """

    def __init__(
        self,
        cliente_openai: AsyncOpenAI,
        modelo: str = "text-embedding-3-small",
        cache_ttl: int = 3600,
        timeout: int = 5,
    ):
        """
        Inicializa el servicio de embeddings.

        Args:
            cliente_openai: Cliente asíncrono de OpenAI
            modelo: Modelo de embeddings a usar (default: text-embedding-3-small)
            cache_ttl: Tiempo de vida del caché en segundos (default: 3600 = 1 hora)
            timeout: Timeout en segundos para llamadas a OpenAI (default: 5)
        """
        self.client = cliente_openai
        self.model = modelo
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._redis = None

    async def _obtener_redis(self):
        """
        Obtiene el cliente de Redis de forma lazy.

        Returns:
            Cliente de Redis o None si no está disponible
        """
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"⚠️ No se pudo conectar a Redis: {e}")
        return self._redis

    def _generar_clave_cache(self, texto: str) -> str:
        """
        Genera una clave de caché única para el texto.

        Usa SHA256 para generar un hash corto y único del texto,
        lo que permite usar como clave en Redis sin problemas de longitud.

        Args:
            texto: Texto a cachear

        Returns:
            Clave de caché con formato: embedding:{modelo}:{hash}
        """
        # Generar hash del texto para clave corta
        texto_hash = hashlib.sha256(texto.encode()).hexdigest()[:16]
        return f"embedding:{self.model}:{texto_hash}"

    async def generar_embedding(
        self,
        texto: str,
        usar_cache: bool = True,
    ) -> Optional[List[float]]:
        """
        Genera embedding para un texto individual.

        Este método genera un embedding vectorial de 1536 dimensiones
        utilizando el modelo configurado de OpenAI. Si el caché está
        habilitado y el texto ya fue procesado, retorna el resultado
        cacheado para reducir costos.

        Args:
            texto: Texto a convertir en embedding
            usar_cache: Si True, intenta usar caché de Redis primero

        Returns:
            Lista de 1536 floats representando el embedding, o None si falló

        Raises:
            ValueError: Si el texto está vacío o es solo espacios

        Ejemplo:
            >>> embedding = await servicio.generar_embedding("Plomería y Fontanería")
            >>> print(len(embedding))  # 1536
        """
        if not texto or not texto.strip():
            raise ValueError("El texto no puede estar vacío")

        # Limpiar texto
        texto = texto.strip()

        # Verificar caché si está habilitado
        if usar_cache:
            try:
                redis = await self._obtener_redis()
                if redis:
                    clave_cache = self._generar_clave_cache(texto)
                    cachado = await redis.get(clave_cache)
                    if cachado:
                        logger.debug(f"✅ Cache hit para: {texto[:50]}...")
                        return json.loads(cachado)
            except Exception as e:
                logger.warning(f"⚠️ Error leyendo caché: {e}")

        # Generar embedding con OpenAI
        try:
            logger.info(f"🔄 Generando embedding para: {texto[:50]}...")
            respuesta = await self.client.embeddings.create(
                input=texto,
                model=self.model,
                timeout=self.timeout,
            )

            embedding = respuesta.data[0].embedding

            # Guardar en caché
            if usar_cache:
                try:
                    redis = await self._obtener_redis()
                    if redis:
                        clave_cache = self._generar_clave_cache(texto)
                        await redis.set(
                            clave_cache,
                            json.dumps(embedding),
                            expire=self.cache_ttl,
                        )
                        logger.debug(f"💾 Embedding cacheado: {clave_cache}")
                except Exception as e:
                    logger.warning(f"⚠️ Error guardando caché: {e}")

            logger.info(f"✅ Embedding generado: {len(embedding)} dimensiones")
            return embedding

        except Exception as e:
            logger.error(f"❌ Error generando embedding: {e}")
            return None

    async def generar_embedding_lote(
        self,
        textos: List[str],
        usar_cache: bool = True,
    ) -> List[Optional[List[float]]]:
        """
        Genera embeddings para múltiples textos en lote.

        Este método procesa una lista de textos y genera un embedding
        para cada uno. Es útil para backfill o procesamiento por lotes.

        Args:
            textos: Lista de textos a convertir
            usar_cache: Si True, usa caché para textos ya procesados

        Returns:
            Lista de embeddings (misma longitud que textos de entrada)
            Cada elemento es List[float] o None si falló para ese texto

        Ejemplo:
            >>> servicios = ["Plomería", "Electricidad", "Gasfitería"]
            >>> embeddings = await servicio.generar_embedding_lote(servicios)
            >>> print(len(embeddings))  # 3
        """
        if not textos:
            return []

        embeddings = []

        for texto in textos:
            embedding = await self.generar_embedding(texto, usar_cache=usar_cache)
            embeddings.append(embedding)

        logger.info(f"✅ Lote completado: {len(embeddings)} embeddings generados")
        return embeddings

    async def generar_embedding_servicios(
        self,
        servicios: List[str],
    ) -> List[Optional[List[float]]]:
        """
        Genera embeddings individuales para una lista de servicios.

        A diferencia de generar_embedding_lote() que genera un embedding
        por texto, este método está optimizado específicamente para servicios
        de proveedores, generando un embedding individual por servicio.

        Args:
            servicios: Lista de servicios del proveedor (ej: ["Plomería", "Electricidad"])

        Returns:
            Lista de embeddings, uno por servicio

        Ejemplo:
            >>> servicios = ["Plomería", "Electricidad", "Gasfitería"]
            >>> embeddings = await servicio.generar_embedding_servicios(servicios)
            >>> print(len(embeddings))  # 3
            >>> print(len(embeddings[0]))  # 1536
        """
        if not servicios:
            logger.warning("⚠️ Lista de servicios vacía, no se generan embeddings")
            return []

        logger.info(f"🔄 Generando embeddings para {len(servicios)} servicios...")

        # Generar un embedding por servicio individualmente
        embeddings = await self.generar_embedding_lote(servicios, usar_cache=True)

        embeddings_validos = [e for e in embeddings if e is not None]
        logger.info(f"✅ {len(embeddings_validos)}/{len(servicios)} embeddings generados exitosamente")

        return embeddings

    async def verificar_embedding_en_cache(self, texto: str) -> bool:
        """
        Verifica si un embedding ya existe en caché.

        Args:
            texto: Texto a verificar

        Returns:
            True si existe en caché, False en caso contrario
        """
        try:
            redis = await self._obtener_redis()
            if redis:
                clave_cache = self._generar_clave_cache(texto)
                return await redis.exists(clave_cache) > 0
        except Exception as e:
            logger.warning(f"⚠️ Error verificando caché: {e}")

        return False

    async def limpiar_cache(self, texto: Optional[str] = None) -> int:
        """
        Limpia embeddings de la caché.

        Args:
            texto: Si se proporciona, limpia solo ese texto.
                   Si es None, limpia todos los embeddings del modelo.

        Returns:
            Número de claves eliminadas

        Ejemplo:
            >>> # Limpiar un texto específico
            >>> await servicio.limpiar_cache("Plomería")
            >>> # Limpiar todos los embeddings
            >>> await servicio.limpiar_cache()
        """
        try:
            redis = await self._obtener_redis()
            if not redis:
                logger.warning("⚠️ Redis no disponible para limpiar caché")
                return 0

            if texto:
                clave = self._generar_clave_cache(texto)
                eliminados = await redis.delete(clave)
                logger.info(f"🗑️ Eliminado {eliminados} embedding de caché")
            else:
                # Eliminar todos los embeddings del modelo actual
                patron = f"embedding:{self.model}:*"
                claves = await redis.keys(patron)
                if claves:
                    eliminados = await redis.delete(*claves)
                    logger.info(f"🗑️ Eliminados {eliminados} embeddings de caché")
                else:
                    eliminados = 0

            return eliminados

        except Exception as e:
            logger.error(f"❌ Error limpiando caché: {e}")
            return 0
