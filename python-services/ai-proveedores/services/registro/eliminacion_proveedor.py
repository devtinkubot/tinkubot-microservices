"""
Servicio de eliminación de registros de proveedores.

Elimina de forma integral: perfil, servicios, assets de storage y estado de caché/flujo.
"""

import logging
from typing import Any, Dict, Optional, Set
from urllib.parse import unquote, urlparse

from infrastructure.database import run_supabase
from infrastructure.storage.almacenamiento_imagenes import SUPABASE_PROVIDERS_BUCKET

logger = logging.getLogger(__name__)

_RUTAS_POR_DEFECTO_EXTS = ("jpg", "jpeg", "png", "webp")


async def eliminar_registro_proveedor(
    supabase: Any,
    telefono: str,
) -> Dict[str, Any]:
    """
    Elimina completamente el registro de un proveedor.
    """
    if not telefono:
        raise ValueError("telefono es requerido")

    resultado = {
        "success": False,
        "message": "",
        "deleted_from_db": False,
        "deleted_from_cache": False,
        "deleted_related_services": False,
        "deleted_storage_assets": False,
    }

    if not supabase:
        resultado["message"] = "Cliente Supabase no disponible"
        return resultado

    try:
        logger.info("🗑️ Iniciando eliminación integral del proveedor %s", telefono)

        perfil = await _obtener_perfil_para_eliminacion(supabase, telefono)
        provider_id = perfil.get("id") if perfil else None

        if provider_id:
            await run_supabase(
                lambda: supabase.table("provider_services")
                .delete()
                .eq("provider_id", provider_id)
                .execute(),
                label="provider_services.delete_on_provider_removal",
            )
            resultado["deleted_related_services"] = True
            logger.info("✅ Servicios relacionados eliminados para provider_id=%s", provider_id)

        rutas_storage = _obtener_rutas_storage(perfil, provider_id)
        resultado["deleted_storage_assets"] = await _eliminar_assets_storage(
            supabase=supabase,
            rutas=rutas_storage,
        )

        await run_supabase(
            lambda: supabase.table("providers")
            .delete()
            .eq("phone", telefono)
            .execute(),
            label="providers.delete_by_phone",
        )
        resultado["deleted_from_db"] = True
        logger.info("✅ Proveedor %s eliminado de la base de datos", telefono)

        from flows.sesion import marcar_perfil_eliminado
        from flows.sesion.gestor_flujo import reiniciar_flujo

        resultado["deleted_from_cache"] = await marcar_perfil_eliminado(telefono)
        await reiniciar_flujo(telefono)
        logger.info("✅ Caché y flujo conversacional limpiados para %s", telefono)

        resultado["success"] = True
        resultado["message"] = "Tu registro ha sido eliminado correctamente."
        logger.info("✨ Eliminación completada exitosamente para %s", telefono)

    except Exception as exc:
        logger.error("❌ Error al eliminar proveedor %s: %s", telefono, exc, exc_info=True)
        resultado["message"] = (
            "Hubo un error al eliminar tu registro. Por favor, intenta nuevamente."
        )

    return resultado


async def _obtener_perfil_para_eliminacion(
    supabase: Any, telefono: str
) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("providers")
        .select("id,dni_front_photo_url,dni_back_photo_url,face_photo_url")
        .eq("phone", telefono)
        .limit(1)
        .execute(),
        label="providers.lookup_for_delete",
    )
    if respuesta.data:
        return respuesta.data[0]
    return None


def _obtener_rutas_storage(
    perfil: Optional[Dict[str, Any]],
    provider_id: Optional[str],
) -> list[str]:
    rutas: Set[str] = set()
    if perfil:
        for campo in ("dni_front_photo_url", "dni_back_photo_url", "face_photo_url"):
            ruta = _extraer_path_storage_desde_url(perfil.get(campo))
            if ruta:
                rutas.add(ruta)

    if provider_id:
        for extension in _RUTAS_POR_DEFECTO_EXTS:
            rutas.add(f"dni-fronts/{provider_id}.{extension}")
            rutas.add(f"dni-backs/{provider_id}.{extension}")
            rutas.add(f"faces/{provider_id}.{extension}")

    return sorted(rutas)


def _extraer_path_storage_desde_url(valor: Any) -> Optional[str]:
    if not isinstance(valor, str):
        return None

    texto = valor.strip()
    if not texto:
        return None

    if "://" not in texto:
        limpio = texto.lstrip("/")
        prefijo_bucket = f"{SUPABASE_PROVIDERS_BUCKET}/"
        if limpio.startswith(prefijo_bucket):
            return limpio[len(prefijo_bucket):]
        return limpio

    parsed = urlparse(texto)
    path = unquote(parsed.path or "")
    if not path:
        return None

    bucket = SUPABASE_PROVIDERS_BUCKET
    marcadores = (
        f"/storage/v1/object/public/{bucket}/",
        f"/storage/v1/object/sign/{bucket}/",
        f"/storage/v1/object/{bucket}/",
    )
    for marcador in marcadores:
        if marcador in path:
            return path.split(marcador, 1)[1].lstrip("/")

    partes = [segmento for segmento in path.split("/") if segmento]
    if bucket in partes:
        indice = partes.index(bucket)
        resto = partes[indice + 1:]
        if resto:
            return "/".join(resto)

    return None


async def _eliminar_assets_storage(
    *,
    supabase: Any,
    rutas: list[str],
) -> bool:
    if not rutas:
        return True

    if not SUPABASE_PROVIDERS_BUCKET:
        logger.warning("⚠️ Bucket de proveedores no configurado; no se eliminan assets")
        return False

    try:
        await run_supabase(
            lambda: supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).remove(rutas),
            label="storage.remove_provider_assets",
        )
        logger.info("✅ Eliminación de assets solicitada para %s rutas", len(rutas))
        return True
    except Exception as exc:
        logger.warning("⚠️ No se pudieron eliminar assets de storage: %s", exc)
        return False
