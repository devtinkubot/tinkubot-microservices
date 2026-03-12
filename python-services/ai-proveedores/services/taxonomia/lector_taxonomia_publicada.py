"""Lector de la taxonomía publicada activa con caché local por TTL."""

from __future__ import annotations

import logging
from copy import deepcopy
from time import monotonic
from typing import Any, Callable, Dict, List, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase
from infrastructure.database.client import get_supabase_client

logger = logging.getLogger(__name__)

TaxonomiaPublicada = Dict[str, Any]

_TAXONOMIA_VACIA: TaxonomiaPublicada = {
    "publication": None,
    "version": None,
    "domains": [],
}
_STATUSES_PUBLICADOS = {"active", "published"}


class LectorTaxonomiaPublicada:
    """Lee la última publicación activa de taxonomía desde Supabase."""

    def __init__(
        self,
        supabase: Optional[Any] = None,
        ttl_segundos: Optional[int] = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._supabase = supabase
        self._ttl_segundos = (
            ttl_segundos
            if ttl_segundos is not None
            else configuracion.ttl_cache_taxonomia_segundos
        )
        self._clock = clock
        self._cache: Optional[TaxonomiaPublicada] = None
        self._cache_expira_en: float = 0.0

    async def obtener_taxonomia_publicada(
        self,
        *,
        force_refresh: bool = False,
    ) -> TaxonomiaPublicada:
        """Obtiene la taxonomía publicada activa usando caché local por TTL."""
        if not force_refresh and self._cache_vigente():
            return deepcopy(self._cache)

        taxonomia = await self._leer_desde_origen()
        self._cache = taxonomia
        self._cache_expira_en = self._clock() + max(self._ttl_segundos, 0)
        return deepcopy(taxonomia)

    async def obtener_version_publicada(self, *, force_refresh: bool = False) -> Optional[str]:
        """Devuelve la versión publicada activa."""
        taxonomia = await self.obtener_taxonomia_publicada(force_refresh=force_refresh)
        version = taxonomia.get("version")
        return version if isinstance(version, str) and version.strip() else None

    def invalidar_cache(self) -> None:
        """Limpia el caché local del lector."""
        self._cache = None
        self._cache_expira_en = 0.0

    def _cache_vigente(self) -> bool:
        return self._cache is not None and self._clock() < self._cache_expira_en

    async def _leer_desde_origen(self) -> TaxonomiaPublicada:
        supabase = self._supabase or get_supabase_client()
        if supabase is None:
            return deepcopy(_TAXONOMIA_VACIA)

        if self._cache is not None:
            try:
                return await self._leer_publicacion_desde_supabase(supabase)
            except Exception as exc:
                logger.warning(
                    "⚠️ Error leyendo taxonomía publicada; usando caché previa: %s",
                    exc,
                )
                return deepcopy(self._cache)

        try:
            return await self._leer_publicacion_desde_supabase(supabase)
        except Exception as exc:
            logger.warning(
                "⚠️ Error leyendo taxonomía publicada; devolviendo vacío seguro: %s",
                exc,
            )
            return deepcopy(_TAXONOMIA_VACIA)

    async def _leer_publicacion_desde_supabase(self, supabase: Any) -> TaxonomiaPublicada:
        publicacion = await self._obtener_publicacion_activa(supabase)
        if publicacion is None:
            return deepcopy(_TAXONOMIA_VACIA)

        dominios = await self._obtener_dominios_activos(supabase)
        aliases_por_dominio = await self._obtener_aliases_activos(supabase)
        canonicos_por_dominio = await self._obtener_canonicos_activos(supabase)
        reglas_por_dominio = await self._obtener_reglas_activas(supabase)

        dominios_compuestos: List[Dict[str, Any]] = []
        for dominio in dominios:
            dominio_id = dominio.get("id")
            if dominio_id is None:
                continue

            dominios_compuestos.append(
                {
                    **dominio,
                    "aliases": aliases_por_dominio.get(dominio_id, []),
                    "canonical_services": canonicos_por_dominio.get(dominio_id, []),
                    "rules": reglas_por_dominio.get(dominio_id, []),
                }
            )

        return {
            "publication": publicacion,
            "version": publicacion.get("version"),
            "domains": dominios_compuestos,
        }

    async def _obtener_publicacion_activa(self, supabase: Any) -> Optional[Dict[str, Any]]:
        respuesta = await run_supabase(
            lambda: supabase.table("service_taxonomy_publications")
            .select("id,version,status,published_by,published_at,notes")
            .order("published_at", desc=True)
            .limit(10)
            .execute(),
            label="service_taxonomy_publications.catalog",
        )

        filas = getattr(respuesta, "data", None) or []
        for fila in filas:
            if str(fila.get("status") or "").strip().lower() in _STATUSES_PUBLICADOS:
                return fila
        return None

    async def _obtener_dominios_activos(self, supabase: Any) -> List[Dict[str, Any]]:
        respuesta = await run_supabase(
            lambda: supabase.table("service_domains")
            .select("id,code,display_name,status,description,is_critical")
            .order("code", desc=False)
            .execute(),
            label="service_domains.catalog",
        )
        return [
            fila
            for fila in (getattr(respuesta, "data", None) or [])
            if str(fila.get("status") or "").strip().lower() in _STATUSES_PUBLICADOS
        ]

    async def _obtener_aliases_activos(self, supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
        respuesta = await run_supabase(
            lambda: supabase.table("service_domain_aliases")
            .select("id,domain_id,alias_text,alias_normalized,priority,status")
            .order("priority", desc=False)
            .execute(),
            label="service_domain_aliases.catalog",
        )

        aliases_por_dominio: Dict[Any, List[Dict[str, Any]]] = {}
        for alias in getattr(respuesta, "data", None) or []:
            if not _fila_publicada(alias):
                continue
            dominio_id = alias.get("domain_id")
            if dominio_id is None:
                continue
            aliases_por_dominio.setdefault(dominio_id, []).append(alias)
        return aliases_por_dominio

    async def _obtener_canonicos_activos(self, supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
        respuesta = await run_supabase(
            lambda: supabase.table("service_canonical_services")
            .select(
                "id,domain_id,canonical_name,canonical_normalized,description,"
                "metadata_json,status"
            )
            .order("canonical_normalized", desc=False)
            .execute(),
            label="service_canonical_services.catalog",
        )

        canonicos_por_dominio: Dict[Any, List[Dict[str, Any]]] = {}
        for canonico in getattr(respuesta, "data", None) or []:
            if not _fila_publicada(canonico):
                continue
            dominio_id = canonico.get("domain_id")
            if dominio_id is None:
                continue
            canonicos_por_dominio.setdefault(dominio_id, []).append(canonico)
        return canonicos_por_dominio

    async def _obtener_reglas_activas(self, supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
        respuesta = await run_supabase(
            lambda: supabase.table("service_precision_rules")
            .select(
                "id,domain_id,required_dimensions,generic_examples,"
                "sufficient_examples,client_prompt_template,provider_prompt_template"
            )
            .execute(),
            label="service_precision_rules.catalog",
        )

        reglas_por_dominio: Dict[Any, List[Dict[str, Any]]] = {}
        for regla in getattr(respuesta, "data", None) or []:
            if not _fila_publicada(regla):
                continue
            dominio_id = regla.get("domain_id")
            if dominio_id is None:
                continue
            reglas_por_dominio.setdefault(dominio_id, []).append(regla)
        return reglas_por_dominio


def _fila_publicada(fila: Dict[str, Any]) -> bool:
    if "is_active" in fila:
        return bool(fila.get("is_active"))
    status = str(fila.get("status") or "").strip().lower()
    return status in _STATUSES_PUBLICADOS or not status
