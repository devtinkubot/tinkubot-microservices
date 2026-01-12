"""
Phone Type Detector - Detecta si un phone es c.us o lid.
"""

from enum import Enum
from typing import Optional


class PhoneType(Enum):
    """Tipos de phone soportados."""
    C_US = "c.us"  # WhatsApp Business ID normal
    LID = "lid"    # Lead ID (necesita número real)
    UNKNOWN = "unknown"


class PhoneTypeDetector:
    """Detecta el tipo de phone basado en su formato."""

    @staticmethod
    def detect(phone: str) -> PhoneType:
        """
        Detecta el tipo de phone.

        Args:
            phone: Número de teléfono crudo (ej: +593987654321@c.us)

        Returns:
            PhoneType: Tipo de phone detectado
        """
        if not phone:
            return PhoneType.UNKNOWN

        phone_str = str(phone).strip().lower()

        if phone_str.endswith("@lid"):
            return PhoneType.LID
        elif phone_str.endswith("@c.us"):
            return PhoneType.C_US

        return PhoneType.UNKNOWN

    @staticmethod
    def is_lid(phone: str) -> bool:
        """Verifica si el phone es tipo LID."""
        return PhoneTypeDetector.detect(phone) == PhoneType.LID

    @staticmethod
    def is_c_us(phone: str) -> bool:
        """Verifica si el phone es tipo c.us."""
        return PhoneTypeDetector.detect(phone) == PhoneType.C_US

    @staticmethod
    def extract_real_number(phone: str) -> Optional[str]:
        """
        Extrae el número real sin sufijo.

        Args:
            phone: Phone crudo (ej: +593987654321@c.us)

        Returns:
            Número extraído o None
        """
        if not phone:
            return None

        phone_str = str(phone).strip()

        # Remover @c.us o @lid
        if "@c.us" in phone_str.lower():
            return phone_str.lower().replace("@c.us", "")
        elif "@lid" in phone_str.lower():
            return phone_str.lower().replace("@lid", "")

        return phone_str

    @staticmethod
    def normalize_to_c_us_format(phone: str) -> Optional[str]:
        """
        Normaliza un número de teléfono ecuatoriano a formato @c.us.

        Convierte:
        - 0991234567 -> +593991234567@c.us
        - +593991234567 -> +593991234567@c.us
        - +593991234567@c.us -> +593991234567@c.us

        Args:
            phone: Número de teléfono en cualquier formato

        Returns:
            Número normalizado en formato @c.us o None si es inválido
        """
        if not phone:
            return None

        # Si ya tiene formato @c.us, retornarlo tal cual
        phone_str = str(phone).strip()
        if phone_str.endswith("@c.us"):
            return phone_str

        # Remover @lid si existe
        if phone_str.endswith("@lid"):
            phone_str = phone_str.lower().replace("@lid", "")

        # Remover todos los caracteres no numéricos excepto +
        cleaned = ""
        for char in phone_str:
            if char.isdigit() or char == "+":
                cleaned += char

        # Remover el + si existe para procesamiento
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]

        # Validar que sea numérico y tenga 10 dígitos (Ecuador)
        if not cleaned.isdigit():
            return None

        # Si es 09XXXXXXXX (formato celular Ecuador), convertir a +5939XXXXXXXX
        if len(cleaned) == 10 and cleaned.startswith("09"):
            cleaned = "593" + cleaned[1:]  # Remover el 0 inicial y agregar 593

        # Si es 5939XXXXXXXX (ya tiene código de país), usarlo tal cual
        elif len(cleaned) == 12 and cleaned.startswith("5939"):
            pass  # Ya está en formato correcto

        else:
            return None  # Formato no válido

        # Agregar el + y el sufijo @c.us
        return f"+{cleaned}@c.us"
