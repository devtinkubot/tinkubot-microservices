"""
Catálogo Dinámico de Servicios con cache en Redis.

Este módulo implementa un catálogo de servicios que:
1. Se almacena en Supabase (persistente, actualizable sin reinicio)
2. Cachea en Redis para acceso rápido
3. Se auto-actualiza cuando el cache expira
4. Permite actualizaciones manuales via API

VENTAJAS:
- ✅ No requiere rebuild/restart del servicio
- ✅ Se puede actualizar via SQL o admin panel
- ✅ Cache Redis para performance (TTL configurable)
- ✅ Auto-refresh cuando expira el cache
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional, Set

from infrastructure.redis import redis_client
from utils.db_utils import run_supabase
from utils.services_utils import _normalize_text_for_matching

# Logger
logger = logging.getLogger(__name__)

# Configuración
SERVICE_SYNONYMS_CACHE_KEY = "service_synonyms:catalog"
SERVICE_SYNONYMS_CACHE_TTL = int(os.getenv("SERVICE_SYNONYMS_CACHE_TTL", "3600"))  # 1 hora por defecto


class DynamicServiceCatalog:
    """Catálogo dinámico de servicios con cache en Redis.

    Responsabilidades:
    - Cargar sinónimos desde Supabase
    - Mantener cache en Redis
    - Auto-refrescar cuando expire el cache
    - Permitir búsqueda de profesión canónica por sinónimo
    """

    def __init__(self, supabase_client):
        """Inicializa el catálogo dinámico.

        Args:
            supabase_client: Cliente Supabase para cargar sinónimos
        """
        self.supabase = supabase_client
        self._cache: Optional[Dict[str, Set[str]]] = None
        self._reverse_map: Optional[Dict[str, str]] = None  # synonym → canonical
        self._last_load_at: Optional[float] = None

    async def get_synonyms(self, force_refresh: bool = False) -> Dict[str, Set[str]]:
        """Obtener diccionario de sinónimos (canonical → {synonyms}).

        Args:
            force_refresh: Si True, recarga desde Supabase ignorando el cache

        Returns:
            Dict con profesión canónica como key y set de sinónimos como value
        """
        # Verificar si tenemos cache en memoria y es válido
        if not force_refresh and self._cache is not None:
            return self._cache

        # Intentar cargar desde Redis
        try:
            cached_data = await redis_client.get(SERVICE_SYNONYMS_CACHE_KEY)
            if cached_data and not force_refresh:
                self._cache = json.loads(cached_data)
                self._build_reverse_map()
                logger.info(
                    f"✅ Catálogo de servicios cargado desde Redis cache "
                    f"({len(self._cache)} profesiones)"
                )
                return self._cache
        except Exception as e:
            logger.warning(f"⚠️ Error cargando catálogo desde Redis: {e}")

        # Cargar desde Supabase
        return await self._load_from_supabase()

    async def _load_from_supabase(self) -> Dict[str, Set[str]]:
        """Carga sinónimos desde Supabase y actualiza cache.

        Returns:
            Dict con profesión canónica → set de sinónimos
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("service_synonyms")
                .select("canonical_profession", "synonym")
                .eq("active", True)
                .execute(),
                label="service_synonyms.load_all"
            )

            if not result.data:
                logger.warning("⚠️ No se encontraron sinónimos en Supabase")
                return {}

            # Construir diccionario canonical → {synonyms}
            catalog: Dict[str, Set[str]] = {}
            for row in result.data:
                canonical = row["canonical_profession"]
                synonym = row["synonym"]

                if canonical not in catalog:
                    catalog[canonical] = set()
                catalog[canonical].add(synonym)

            # Guardar en cache Redis
            await redis_client.set(
                SERVICE_SYNONYMS_CACHE_KEY,
                json.dumps(catalog),
                expire=SERVICE_SYNONYMS_CACHE_TTL
            )

            # Actualizar cache en memoria
            self._cache = catalog
            self._build_reverse_map()
            self._last_load_at = asyncio.get_event_loop().time()

            logger.info(
                f"✅ Catálogo de servicios cargado desde Supabase "
                f"({len(catalog)} profesiones, {sum(len(s) for s in catalog.values())} sinónimos)"
            )

            return catalog

        except Exception as e:
            logger.error(f"❌ Error cargando catálogo desde Supabase: {e}")
            # Retornar cache en memoria si existe, aunque esté viejo
            return self._cache or {}

    def _build_reverse_map(self):
        """Construye mapa inverso: synonym → canonical.

        Útil para búsqueda rápida de profesión canónica.
        """
        if not self._cache:
            return

        self._reverse_map = {}
        for canonical, synonyms in self._cache.items():
            # Incluir la canonical como sinónimo de sí misma
            self._reverse_map[_normalize_text_for_matching(canonical)] = canonical

            for synonym in synonyms:
                normalized = _normalize_text_for_matching(synonym)
                if normalized:
                    self._reverse_map[normalized] = canonical

    async def find_profession(self, text: str) -> Optional[str]:
        """Busca profesión canónica dado un texto.

        Args:
            text: Texto de búsqueda (ej: "gestor de redes sociales")

        Returns:
            Profesión canónica (ej: "marketing") o None si no encuentra
        """
        # Asegurar que el catálogo está cargado
        await self.get_synonyms()

        if not self._reverse_map:
            return None

        # Normalizar texto de búsqueda
        normalized = _normalize_text_for_matching(text)
        if not normalized:
            return None

        # Buscar coincidencia exacta primero
        if normalized in self._reverse_map:
            return self._reverse_map[normalized]

        # Buscar coincidencia parcial (contiene)
        for synonym, canonical in self._reverse_map.items():
            if normalized in synonym or synonym in normalized:
                return canonical

        return None

    async def get_all_canonical_professions(self) -> list[str]:
        """Retorna lista de todas las profesiones canónicas."""
        catalog = await self.get_synonyms()
        return list(catalog.keys())

    async def refresh_cache(self):
        """Fuerza la recarga del catálogo desde Supabase.

        Útil para actualizar después de modificar la tabla via SQL o API.
        """
        logger.info("🔄 Forzando recarga de catálogo de servicios...")
        await self.get_synonyms(force_refresh=True)


# ============================================================================
# INSTANCIA GLOBAL (se inicializa en main.py)
# ============================================================================

dynamic_service_catalog: Optional[DynamicServiceCatalog] = None


def initialize_dynamic_service_catalog(supabase_client) -> None:
    """Inicializa el catálogo dinámico de servicios.

    Args:
        supabase_client: Cliente Supabase (opcional)
    """
    global dynamic_service_catalog

    if supabase_client:
        dynamic_service_catalog = DynamicServiceCatalog(supabase_client)
        logger.info("✅ DynamicServiceCatalog inicializado")
    else:
        dynamic_service_catalog = None
        logger.warning("⚠️ DynamicServiceCatalog deshabilitado (sin Supabase)")
