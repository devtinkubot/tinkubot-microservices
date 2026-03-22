"""Utilidades para manejar redes sociales fijas de proveedores."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from services.servicios_proveedor.utilidades import limpiar_espacios

SOCIAL_NETWORK_FACEBOOK = "facebook"
SOCIAL_NETWORK_INSTAGRAM = "instagram"
SOCIAL_NETWORKS = {
    SOCIAL_NETWORK_FACEBOOK,
    SOCIAL_NETWORK_INSTAGRAM,
}
SOCIAL_SKIP_VALUES = {"omitir", "na", "n/a", "ninguno"}


def _normalizar_username_crudo(valor: Optional[str]) -> Optional[str]:
    texto = limpiar_espacios(valor)
    if not texto:
        return None
    texto = texto.strip().strip("/")
    if texto.startswith("@"):
        texto = texto[1:]
    return texto or None


def construir_url_red_social(
    tipo_red: Optional[str],
    username: Optional[str],
) -> Optional[str]:
    username_normalizado = _normalizar_username_crudo(username)
    if not username_normalizado or tipo_red not in SOCIAL_NETWORKS:
        return None
    if tipo_red == SOCIAL_NETWORK_FACEBOOK:
        return f"https://facebook.com/{username_normalizado}"
    return f"https://instagram.com/{username_normalizado}"


def extraer_username_desde_url(
    url_o_username: Optional[str],
    tipo_red: str,
) -> Optional[str]:
    texto = limpiar_espacios(url_o_username)
    if not texto:
        return None
    if texto.lower() in SOCIAL_SKIP_VALUES:
        return None

    texto_parseable = texto
    if "://" not in texto_parseable and any(
        dominio in texto_parseable.lower()
        for dominio in ("facebook.com", "fb.com", "instagram.com", "instagr.am")
    ):
        texto_parseable = f"https://{texto_parseable}"

    if "://" not in texto_parseable:
        return _normalizar_username_crudo(texto_parseable)

    parsed = urlparse(texto_parseable)
    host = parsed.netloc.lower()
    path_parts = [parte for parte in parsed.path.split("/") if parte]

    if tipo_red == SOCIAL_NETWORK_FACEBOOK:
        if not any(dominio in host for dominio in ("facebook.com", "fb.com")):
            return None
        if path_parts and path_parts[0] != "profile.php":
            return _normalizar_username_crudo(path_parts[0])
        if parsed.path.endswith("profile.php"):
            profile_id = parse_qs(parsed.query).get("id", [None])[0]
            return _normalizar_username_crudo(profile_id)
        return None

    if tipo_red == SOCIAL_NETWORK_INSTAGRAM:
        if not any(dominio in host for dominio in ("instagram.com", "instagr.am")):
            return None
        if path_parts:
            return _normalizar_username_crudo(path_parts[0])
        return None

    return None


def parsear_username_red_social(
    texto_mensaje: Optional[str],
    tipo_red: str,
) -> Dict[str, Optional[str]]:
    username = extraer_username_desde_url(texto_mensaje, tipo_red)
    return {
        "type": tipo_red if username else None,
        "username": username,
        "url": construir_url_red_social(tipo_red, username),
    }


def resolver_redes_sociales(datos: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    fuente = datos or {}
    facebook_username = _normalizar_username_crudo(fuente.get("facebook_username"))
    instagram_username = _normalizar_username_crudo(fuente.get("instagram_username"))

    legacy_url = limpiar_espacios(fuente.get("social_media_url"))
    legacy_type = limpiar_espacios(fuente.get("social_media_type")).lower()

    if not facebook_username and legacy_type == SOCIAL_NETWORK_FACEBOOK:
        facebook_username = extraer_username_desde_url(
            legacy_url,
            SOCIAL_NETWORK_FACEBOOK,
        )
    if not instagram_username and legacy_type == SOCIAL_NETWORK_INSTAGRAM:
        instagram_username = extraer_username_desde_url(
            legacy_url,
            SOCIAL_NETWORK_INSTAGRAM,
        )

    return {
        "facebook_username": facebook_username,
        "instagram_username": instagram_username,
        "facebook_url": construir_url_red_social(
            SOCIAL_NETWORK_FACEBOOK, facebook_username
        ),
        "instagram_url": construir_url_red_social(
            SOCIAL_NETWORK_INSTAGRAM, instagram_username
        ),
    }


def construir_payload_legacy_red_social(
    *,
    facebook_username: Optional[str],
    instagram_username: Optional[str],
    preferred_type: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    preferida = (preferred_type or "").strip().lower()
    if preferida == SOCIAL_NETWORK_FACEBOOK and facebook_username:
        return {
            "social_media_url": construir_url_red_social(
                SOCIAL_NETWORK_FACEBOOK,
                facebook_username,
            ),
            "social_media_type": SOCIAL_NETWORK_FACEBOOK,
        }
    if preferida == SOCIAL_NETWORK_INSTAGRAM and instagram_username:
        return {
            "social_media_url": construir_url_red_social(
                SOCIAL_NETWORK_INSTAGRAM,
                instagram_username,
            ),
            "social_media_type": SOCIAL_NETWORK_INSTAGRAM,
        }
    if instagram_username:
        return {
            "social_media_url": construir_url_red_social(
                SOCIAL_NETWORK_INSTAGRAM,
                instagram_username,
            ),
            "social_media_type": SOCIAL_NETWORK_INSTAGRAM,
        }
    if facebook_username:
        return {
            "social_media_url": construir_url_red_social(
                SOCIAL_NETWORK_FACEBOOK,
                facebook_username,
            ),
            "social_media_type": SOCIAL_NETWORK_FACEBOOK,
        }
    return {"social_media_url": None, "social_media_type": None}
