"""Utilidades para construir URLs de medios almacenados."""

from typing import Optional


def _extraer_ruta_almacenamiento(url_cruda: str, bucket: str) -> Optional[str]:
    limpia = (url_cruda or "").strip()
    if not limpia:
        return None
    sin_query = limpia.split("?", 1)[0].lstrip("/")

    markers = [
        f"storage/v1/object/sign/{bucket}/",
        f"storage/v1/object/public/{bucket}/",
        f"storage/v1/object/{bucket}/",
        "admin/providers/image/",
    ]
    for marker in markers:
        if marker in sin_query:
            return sin_query.split(marker, 1)[-1].lstrip("/")

    if "/" not in sin_query:
        return f"faces/{sin_query}"

    return sin_query


def construir_url_media_publica(
    url_cruda: Optional[str],
    *,
    supabase,
    bucket: str,
    supabase_base_url: str,
) -> Optional[str]:
    if not url_cruda:
        return None

    texto = str(url_cruda).strip()
    if not texto:
        return None

    ruta_almacenamiento = _extraer_ruta_almacenamiento(texto, bucket)
    if not ruta_almacenamiento:
        return texto if "://" in texto else None

    try:
        if supabase and bucket:
            firmado = supabase.storage.from_(bucket).create_signed_url(
                ruta_almacenamiento, 6 * 60 * 60
            )
            if isinstance(firmado, dict):
                url_firmada = firmado.get("signedURL") or firmado.get("signed_url")
            else:
                url_firmada = getattr(firmado, "signedURL", None) or getattr(
                    firmado, "signed_url", None
                )
            if url_firmada:
                return url_firmada
            url_publica = supabase.storage.from_(bucket).get_public_url(
                ruta_almacenamiento
            )
            if url_publica:
                return url_publica
    except Exception:
        pass

    base_supabase = (supabase_base_url or "").rstrip("/")
    if base_supabase and bucket:
        return f"{base_supabase}/storage/v1/object/public/{bucket}/{ruta_almacenamiento}"

    return ruta_almacenamiento
