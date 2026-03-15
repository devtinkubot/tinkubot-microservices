"""Utilidades para preparar la ficha de detalle de proveedores."""

from typing import Any, Dict

from infrastructure.storage.rutas import construir_url_media_publica


def preparar_proveedor_para_detalle(
    proveedor: Dict[str, Any],
    *,
    supabase,
    bucket: str,
    supabase_base_url: str,
) -> Dict[str, Any]:
    """Devuelve una copia del proveedor con la foto lista para UI interactiva."""
    proveedor_preparado = dict(proveedor or {})
    foto_cruda = (
        proveedor_preparado.get("face_photo_url")
        or proveedor_preparado.get("selfie_url")
        or proveedor_preparado.get("photo_url")
    )

    foto_resuelta = construir_url_media_publica(
        foto_cruda,
        supabase=supabase,
        bucket=bucket,
        supabase_base_url=supabase_base_url,
    )

    foto_resuelta = str(foto_resuelta or "").strip()
    if foto_resuelta and "://" in foto_resuelta and not foto_resuelta.endswith("?"):
        proveedor_preparado["face_photo_url"] = foto_resuelta
    else:
        proveedor_preparado.pop("face_photo_url", None)

    return proveedor_preparado
