"""
Actualizador de servicios de proveedores.

Este módulo contiene la lógica para actualizar los servicios
ofrecidos por un proveedor en la base de datos.
"""

import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, List, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.servicios_proveedor.utilidades import (
    sanitizar_lista_servicios as sanitizar_servicios,
)
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def actualizar_servicios(proveedor_id: str, servicios: List[str]) -> List[str]:
    """
    Actualiza los servicios del proveedor en Supabase.

    Args:
        proveedor_id: UUID del proveedor
        servicios: Lista de servicios a actualizar

    Returns:
        Lista de servicios limpios y actualizados

    Raises:
        Exception: Si hay un error al actualizar en la base de datos
    """
    from principal import (
        supabase,
        servicio_embeddings,
    )  # Import dinámico para evitar circular import

    if not supabase:
        return sanitizar_servicios(servicios)

    servicios_limpios = sanitizar_servicios(servicios)
    try:
        # Fuente de verdad: provider_services
        # Reemplazo completo para forzar coherencia (incluye eliminación y re-embedding).
        await run_supabase(
            lambda: supabase.table("provider_services")
            .delete()
            .eq("provider_id", proveedor_id)
            .execute(),
            label="provider_services.delete_for_update",
        )

        if servicios_limpios:
            from services.registro import insertar_servicios_proveedor

            resultado_insercion = await insertar_servicios_proveedor(
                supabase=supabase,
                proveedor_id=proveedor_id,
                servicios=servicios_limpios,
                servicio_embeddings=servicio_embeddings,
            )
            inserted_count = int(resultado_insercion.get("inserted_count", 0))
            failed_services = resultado_insercion.get("failed_services", [])
            if inserted_count != len(servicios_limpios) or failed_services:
                raise RuntimeError(
                    "Inserción parcial de servicios: "
                    f"esperados={len(servicios_limpios)} insertados={inserted_count} "
                    f"fallidos={len(failed_services)}"
                )

            servicios_persistidos = await _obtener_servicios_persistidos(
                supabase=supabase,
                proveedor_id=proveedor_id,
            )
            if Counter(servicios_persistidos) != Counter(servicios_limpios):
                raise RuntimeError(
                    "Verificación fallida tras actualización de servicios: "
                    f"esperados={servicios_limpios} persistidos={servicios_persistidos}"
                )

        telefono = await _obtener_telefono_proveedor(supabase, proveedor_id)
        if telefono:
            from flows.sesion import (
                invalidar_cache_perfil_proveedor,
                refrescar_cache_perfil_proveedor,
            )

            await invalidar_cache_perfil_proveedor(telefono)
            try:
                await refrescar_cache_perfil_proveedor(telefono)
            except Exception as exc:
                logger.warning(
                    "⚠️ No se pudo refrescar cache de perfil %s: %s",
                    telefono,
                    exc,
                )
        else:
            logger.warning(
                "⚠️ No se pudo obtener teléfono para refrescar cache (provider_id=%s)",
                proveedor_id,
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


async def _obtener_telefono_proveedor(
    supabase: Any, proveedor_id: str
) -> Optional[str]:
    """Obtiene el teléfono del proveedor para invalidar caché de perfil."""
    try:
        respuesta = await run_supabase(
            lambda: supabase.table("providers")
            .select("phone")
            .eq("id", proveedor_id)
            .limit(1)
            .execute(),
            label="providers.phone_by_id",
        )
        if respuesta.data:
            telefono = respuesta.data[0].get("phone")
            if isinstance(telefono, str) and telefono.strip():
                return telefono.strip()
    except Exception:
        return None
    return None


async def _obtener_servicios_persistidos(
    *,
    supabase: Any,
    proveedor_id: str,
) -> List[str]:
    """Lee provider_services y devuelve servicios sanitizados en orden de despliegue."""
    try:
        respuesta = await run_supabase(
            lambda: supabase.table("provider_services")
            .select("service_name,display_order")
            .eq("provider_id", proveedor_id)
            .order("display_order", desc=False)
            .execute(),
            label="provider_services.verify_after_update",
        )
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo verificar provider_services para {proveedor_id}: {exc}"
        ) from exc

    servicios: List[str] = []
    for fila in respuesta.data or []:
        valor = fila.get("service_name")
        if isinstance(valor, str):
            limpio = valor.strip()
            if limpio:
                servicios.append(limpio)
    return sanitizar_servicios(servicios)
