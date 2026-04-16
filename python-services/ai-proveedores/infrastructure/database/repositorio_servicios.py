from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from services.maintenance.estado_operativo import perfil_profesional_completo
from services.maintenance.revision_catalogo import (
    eliminar_revisiones_catalogo_asociadas_servicio,
)
from utils import sanitizar_lista_servicios as sanitizar_servicios

logger = logging.getLogger(__name__)


class RepositorioServiciosSupabase:
    """Implementación Supabase de IRepositorioServiciosProveedor."""

    def __init__(self, supabase_client) -> None:
        self._supabase = supabase_client

    async def obtener_servicios(self, proveedor_id: str) -> List[str]:
        respuesta = await run_supabase(
            lambda: self._supabase.table("provider_services")
            .select("service_name,display_order")
            .eq("provider_id", proveedor_id)
            .order("display_order", desc=False)
            .execute(),
            label="provider_services.verify_after_update",
        )

        servicios: List[str] = []
        for fila in respuesta.data or []:
            valor = fila.get("service_name")
            if isinstance(valor, str):
                limpio = valor.strip()
                if limpio:
                    servicios.append(limpio)
        return sanitizar_servicios(servicios)

    async def actualizar_servicios(
        self, proveedor_id: str, servicios: List[str]
    ) -> List[str]:
        servicios_limpios = sanitizar_servicios(servicios)
        try:
            await run_supabase(
                lambda: self._supabase.table("provider_services")
                .delete()
                .eq("provider_id", proveedor_id)
                .execute(),
                label="provider_services.delete_for_update",
            )

            if servicios_limpios:
                resultado_insercion = await self._insertar_servicios_proveedor(
                    proveedor_id=proveedor_id,
                    servicios=servicios_limpios,
                )
                inserted_count = int(resultado_insercion.get("inserted_count", 0))
                failed_services = resultado_insercion.get("failed_services", [])
                if inserted_count != len(servicios_limpios) or failed_services:
                    raise RuntimeError(
                        "Inserción parcial de servicios: "
                        f"esperados={len(servicios_limpios)} insertados={inserted_count} "
                        f"fallidos={len(failed_services)}"
                    )

                servicios_persistidos = await self.obtener_servicios(proveedor_id)
                if Counter(servicios_persistidos) != Counter(servicios_limpios):
                    raise RuntimeError(
                        "Verificación fallida tras actualización de servicios: "
                        f"esperados={servicios_limpios} persistidos={servicios_persistidos}"
                    )

            await self._limpiar_flags_y_cache_proveedor(
                proveedor_id=proveedor_id,
                contexto="after_update",
            )
            await self._sincronizar_estado_operativo_proveedor(
                proveedor_id=proveedor_id,
                servicios=servicios_limpios,
            )

            logger.info(
                "✅ Servicios sincronizados para proveedor %s (count=%s)",
                proveedor_id,
                len(servicios_limpios),
            )
        except Exception as exc:
            logger.error(
                "❌ Error actualizando servicios para proveedor %s: %s",
                proveedor_id,
                exc,
            )
            raise

        return servicios_limpios

    async def agregar_servicios(
        self, proveedor_id: str, nuevos_servicios: List[str]
    ) -> List[str]:
        servicios_limpios = sanitizar_servicios(nuevos_servicios)
        if not servicios_limpios:
            if not self._supabase:
                return []
            return await self.obtener_servicios(proveedor_id)

        if not self._supabase:
            return servicios_limpios

        filas_actuales = await self._cargar_filas_servicios_proveedor(
            proveedor_id=proveedor_id,
        )
        servicios_existentes = sanitizar_servicios(
            [str(fila.get("service_name") or "").strip() for fila in filas_actuales]
        )
        servicios_a_insertar = [
            servicio
            for servicio in servicios_limpios
            if servicio not in servicios_existentes
        ]
        if not servicios_a_insertar:
            return servicios_existentes

        resultado_insercion = await self._insertar_servicios_proveedor(
            proveedor_id=proveedor_id,
            servicios=servicios_a_insertar,
            display_order_start=len(filas_actuales),
            mark_first_as_primary=not filas_actuales,
        )
        inserted_count = int(resultado_insercion.get("inserted_count", 0))
        failed_services = resultado_insercion.get("failed_services", [])
        if inserted_count != len(servicios_a_insertar) or failed_services:
            raise RuntimeError(
                "Inserción parcial de servicios incrementales: "
                f"esperados={len(servicios_a_insertar)} insertados={inserted_count} "
                f"fallidos={len(failed_services)}"
            )

        await self._limpiar_flags_y_cache_proveedor(
            proveedor_id=proveedor_id,
            contexto="after_incremental_add",
        )
        await self._sincronizar_estado_operativo_proveedor(
            proveedor_id=proveedor_id,
            servicios=servicios_existentes + servicios_a_insertar,
        )

        servicios_persistidos = await self.obtener_servicios(proveedor_id)
        logger.info(
            "✅ Servicios agregados incrementalmente para proveedor %s (count=%s)",
            proveedor_id,
            len(servicios_persistidos),
        )
        return servicios_persistidos

    async def eliminar_servicio(
        self, proveedor_id: str, indice_servicio: int
    ) -> List[str]:
        if not self._supabase:
            return []

        try:
            filas = await self._cargar_filas_servicios_proveedor(
                proveedor_id=proveedor_id,
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudieron cargar los servicios para eliminar proveedor %s: %s",
                proveedor_id,
                exc,
            )
            raise

        if indice_servicio < 0 or indice_servicio >= len(filas):
            raise IndexError(
                f"Índice de servicio fuera de rango para eliminar: {indice_servicio}"
            )

        fila_eliminada = filas[indice_servicio]
        row_id = fila_eliminada.get("id")
        if not row_id:
            raise RuntimeError(f"provider_services sin id para proveedor {proveedor_id}")

        try:
            await self._eliminar_fila_servicio(
                proveedor_id=proveedor_id,
                row_id=row_id,
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudo eliminar provider_services.id=%s para proveedor %s: %s",
                row_id,
                proveedor_id,
                exc,
            )
            raise

        filas_restantes = [fila for idx, fila in enumerate(filas) if idx != indice_servicio]
        try:
            await self._reindexar_filas_restantes(
                proveedor_id=proveedor_id,
                filas_restantes=filas_restantes,
            )
            await self._limpiar_flags_y_cache_proveedor(
                proveedor_id=proveedor_id,
                contexto="after_delete",
            )
            await self._sincronizar_estado_operativo_proveedor(
                proveedor_id=proveedor_id,
                servicios=[
                    str(fila.get("service_name") or "").strip()
                    for fila in filas_restantes
                    if str(fila.get("service_name") or "").strip()
                ],
            )
        except Exception:
            raise

        servicios_persistidos = await self.obtener_servicios(proveedor_id)
        logger.info(
            "✅ Servicio eliminado y servicios reindexados para proveedor %s (count=%s)",
            proveedor_id,
            len(servicios_persistidos),
        )
        return servicios_persistidos

    async def _insertar_servicios_proveedor(
        self,
        *,
        proveedor_id: str,
        servicios: List[str],
        display_order_start: int = 0,
        mark_first_as_primary: bool = True,
    ) -> Dict[str, Any]:
        from services.maintenance.registro_servicios import insertar_servicios_proveedor

        from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings

        return await insertar_servicios_proveedor(
            supabase=self._supabase,
            proveedor_id=proveedor_id,
            servicios=servicios,
            servicio_embeddings=None,
            display_order_start=display_order_start,
            mark_first_as_primary=mark_first_as_primary,
        )

    async def _sincronizar_estado_operativo_proveedor(
        self,
        *,
        proveedor_id: str,
        servicios: List[str],
    ) -> None:
        perfil = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("experience_range")
            .eq("id", proveedor_id)
            .single()
            .execute(),
            label="providers.select_experience_for_service_sync",
        )
        data = getattr(perfil, "data", None) or {}
        await run_supabase(
            lambda: self._supabase.table("providers")
            .update(
                {
                    "onboarding_complete": perfil_profesional_completo(
                        experience_range=data.get("experience_range"),
                        servicios=servicios,
                    )
                }
            )
            .eq("id", proveedor_id)
            .execute(),
            label="providers.update_onboarding_complete_after_service_sync",
        )

    async def _cargar_filas_servicios_proveedor(
        self,
        *,
        proveedor_id: str,
    ) -> List[dict[str, Any]]:
        respuesta = await run_supabase(
            lambda: self._supabase.table("provider_services")
            .select("id,service_name,display_order")
            .eq("provider_id", proveedor_id)
            .order("display_order", desc=False)
            .order("created_at", desc=False)
            .execute(),
            label="provider_services.list_for_delete",
        )
        return list(respuesta.data or [])

    async def _eliminar_fila_servicio(
        self,
        *,
        proveedor_id: str,
        row_id: Any,
    ) -> None:
        await run_supabase(
            lambda: self._supabase.table("provider_services")
            .delete()
            .eq("id", row_id)
            .execute(),
            label="provider_services.delete_single",
        )
        await eliminar_revisiones_catalogo_asociadas_servicio(
            supabase=self._supabase,
            provider_id=proveedor_id,
            published_provider_service_id=str(row_id),
        )
        logger.info(
            "🧹 Servicio eliminado de provider_services (provider_id=%s, row_id=%s)",
            proveedor_id,
            row_id,
        )

    async def _reindexar_filas_restantes(
        self,
        *,
        proveedor_id: str,
        filas_restantes: List[dict[str, Any]],
    ) -> None:
        for nuevo_indice, fila in enumerate(filas_restantes):
            row_id_restante = fila.get("id")
            if not row_id_restante:
                continue
            await self._actualizar_fila_reindexada(
                row_id=row_id_restante,
                nuevo_indice=nuevo_indice,
            )
        logger.info(
            "🧭 Servicios reindexados para proveedor %s (count=%s)",
            proveedor_id,
            len(filas_restantes),
        )

    async def _limpiar_flags_y_cache_proveedor(
        self,
        *,
        proveedor_id: str,
        contexto: str,
    ) -> None:
        await run_supabase(
            lambda: self._supabase.table("providers")
            .update(
                {
                    "service_review_required": False,
                    "generic_services_removed": [],
                }
            )
            .eq("id", proveedor_id)
            .execute(),
            label=f"providers.clear_legacy_generic_services_{contexto}",
        )

        telefono = await self._obtener_telefono_proveedor(proveedor_id)
        if not telefono:
            logger.warning(
                "⚠️ No se pudo obtener teléfono para refrescar cache (provider_id=%s)",
                proveedor_id,
            )
            return

        try:
            from flows.session import invalidar_cache_perfil_proveedor
        except ImportError:
            invalidar_cache_perfil_proveedor = None
        try:
            from flows.session import refrescar_cache_perfil_proveedor
        except ImportError:
            refrescar_cache_perfil_proveedor = None

        if invalidar_cache_proveedor := invalidar_cache_perfil_proveedor:
            await invalidar_cache_proveedor(telefono)
        try:
            if refrescar_cache_perfil_proveedor:
                await refrescar_cache_perfil_proveedor(telefono)
        except Exception as exc:
            logger.warning(
                "⚠️ No se pudo refrescar cache de perfil %s (%s): %s",
                telefono,
                contexto,
                exc,
            )

    async def _actualizar_fila_reindexada(
        self,
        *,
        row_id: Any,
        nuevo_indice: int,
    ) -> None:
        await run_supabase(
            lambda: self._supabase.table("provider_services")
            .update(
                {
                    "display_order": nuevo_indice,
                    "is_primary": nuevo_indice == 0,
                }
            )
            .eq("id", row_id)
            .execute(),
            label="provider_services.reindex_after_delete",
        )
