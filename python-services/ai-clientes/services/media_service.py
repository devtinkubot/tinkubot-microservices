"""
Servicio de gestión de medios y URLs para AI Clientes.

Este módulo contiene:
- Construcción de URLs de medios de Supabase Storage
- Extracción de rutas de almacenamiento
- Formateo de mensajes de conexión con proveedores
- Generación de URLs click-to-chat de WhatsApp
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MediaService:
    """Servicio de operaciones de medios y URLs."""

    def __init__(self, supabase_client, settings, bucket_name: str):
        """
        Inicializa el servicio de medios.

        Args:
            supabase_client: Cliente Supabase para operaciones de storage
            settings: Configuración del sistema
            bucket_name: Nombre del bucket de Supabase Storage
        """
        self.supabase = supabase_client
        self.settings = settings
        self.bucket_name = bucket_name

    def build_public_media_url(self, raw_url: Optional[str]) -> Optional[str]:
        """
        Construye una URL pública o firmada para un medio de Supabase Storage.

        Prioridad:
        1. Intenta crear URL firmada (6 horas de validez)
        2. Si falla, intenta URL pública
        3. Fallback a construcción manual de URL pública

        Args:
            raw_url: URL cruda del medio o ruta de almacenamiento

        Returns:
            URL pública o firmada del medio, o None si no se puede construir
        """
        if not raw_url:
            return None

        text = str(raw_url).strip()
        if not text:
            return None

        storage_path = self._extract_storage_path(text)
        if not storage_path:
            # Si no se pudo extraer, pero es una URL completa, devolverla
            return text if "://" in text else None

        # Intentar URL firmada (si supabase disponible)
        try:
            if self.supabase and self.bucket_name:
                signed = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                    storage_path, 6 * 60 * 60  # 6 horas
                )
                if isinstance(signed, dict):
                    signed_url = signed.get("signedURL") or signed.get("signed_url")
                else:
                    signed_url = getattr(signed, "signedURL", None) or getattr(
                        signed, "signed_url", None
                    )
                if signed_url:
                    return signed_url
                public_url = (
                    self.supabase.storage.from_(self.bucket_name).get_public_url(
                        storage_path
                    )
                )
                if public_url:
                    return public_url
        except Exception:
            # Fallback a URL pública si no se pudo firmar
            pass

        # Fallback a URL pública construida manualmente
        supabase_base = (self.settings.supabase_url or "").rstrip("/")
        if supabase_base and self.bucket_name:
            return f"{supabase_base}/storage/v1/object/public/{self.bucket_name}/{storage_path}"

        return storage_path

    def _extract_storage_path(self, raw_url: str) -> Optional[str]:
        """
        Extrae la ruta de almacenamiento interna de una URL de Supabase.

        Elimina prefijos de endpoints de storage y deja solo la ruta interna
        del archivo en el bucket.

        Args:
            raw_url: URL completa o ruta del archivo

        Returns:
            Ruta interna del archivo en el bucket, o None si no se puede extraer
        """
        cleaned = (raw_url or "").strip()
        if not cleaned:
            return None
        no_query = cleaned.split("?", 1)[0].lstrip("/")

        # Si viene con el prefijo de admin o endpoint de storage, obtener solo la ruta interna
        markers = [
            f"storage/v1/object/sign/{self.bucket_name}/",
            f"storage/v1/object/public/{self.bucket_name}/",
            f"storage/v1/object/{self.bucket_name}/",
            "admin/providers/image/",
        ]
        for marker in markers:
            if marker in no_query:
                return no_query.split(marker, 1)[-1].lstrip("/")

        # Si no tiene slashes, asumir carpeta faces (formato estándar de subida)
        if "/" not in no_query:
            return f"faces/{no_query}"

        return no_query

    def formal_connection_message(
        self, provider: Dict[str, Any], service: str, city: str
    ) -> Dict[str, Any]:
        """
        Genera un mensaje formal de conexión entre cliente y proveedor.

        Incluye:
        - Nombre del proveedor
        - Foto de perfil (selfie) si está disponible
        - Enlace click-to-chat de WhatsApp
        - Información de contacto formateada

        Prioriza real_phone sobre phone para contacto (para proveedores con @lid).

        Args:
            provider: Diccionario con datos del proveedor
            service: Servicio solicitado
            city: Ciudad del servicio

        Returns:
            Diccionario con el mensaje y opcionalmente media_url y media_type
        """
        name = provider.get("name") or provider.get("full_name") or "Proveedor"

        # Prioridad: real_phone (para @lid) > phone > phone_number
        phone_raw = (
            provider.get("real_phone")  # Número real cuando phone es @lid
            or provider.get("phone")     # Phone normal (puede ser @c.us o @lid)
            or provider.get("phone_number")
        )

        link = self.wa_click_to_chat(phone_raw)
        selfie_url_raw = (
            provider.get("face_photo_url")
            or provider.get("selfie_url")
            or provider.get("photo_url")
        )
        selfie_url = self.build_public_media_url(selfie_url_raw)
        selfie_line = (
            "📸 Selfie adjunta."
            if selfie_url
            else "📸 Selfie no disponible por el momento."
        )
        link_line = f"🔗 Abrir chat: {link}" if link else "🔗 Chat disponible via WhatsApp."
        message = (
            f"Proveedor asignado: {name}.\n"
            f"{selfie_line}\n"
            f"{link_line}\n\n"
            f"💬 Chat abierto para coordinar tu servicio."
        )
        payload: Dict[str, Any] = {"response": message}
        if selfie_url:
            payload.update(
                {
                    "media_url": selfie_url,
                    "media_type": "image",
                    "media_caption": message,
                }
            )
        return payload

    @staticmethod
    def pretty_phone(val: Optional[str]) -> str:
        """
        Formatea un número de teléfono para visualización.

        Maneja formatos de WhatsApp:
        - +593987654321@c.us -> +593987654321
        - +593987654321@lid -> LID: 123456
        - 593987654321 -> +593987654321

        Args:
            val: Número de teléfono crudo

        Returns:
            Número formateado para visualización
        """
        raw = (val or "").strip()
        if raw.endswith("@lid"):
            return f"LID: {raw.replace('@lid', '')}" or "LID"
        if raw.endswith("@c.us"):
            raw = raw.replace("@c.us", "")
        if raw and not raw.startswith("+"):
            raw = "+" + raw
        return raw or "s/n"

    @staticmethod
    def wa_click_to_chat(val: Optional[str]) -> str:
        """
        Genera una URL click-to-chat de WhatsApp.

        Args:
            val: Número de teléfono crudo

        Returns:
            URL de WhatsApp click-to-chat (ej: https://wa.me/593987654321)
        """
        raw = (val or "").strip()
        if raw.endswith("@lid"):
            return ""
        if raw.endswith("@c.us"):
            raw = raw.replace("@c.us", "")
        raw = raw.lstrip("+")
        return f"https://wa.me/{raw}"
