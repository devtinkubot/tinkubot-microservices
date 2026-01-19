"""
Input Validation Layer - Fase 1.3 del Plan de Mejoras

Basado en: AUDITORIA_BUSQUEDA_PROVEEDORES.md
Propósito: Prevenir inyección SQL y validar inputs de búsqueda
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SearchQueryValidator(BaseModel):
    """Validator para consultas de búsqueda de proveedores.

    Implementa validación robusta para prevenir:
    - SQL injection
    - XSS
    - Inputs malformados
    """

    city: str = Field(..., min_length=2, max_length=100)
    profession: str = Field(..., min_length=2, max_length=100)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator('city')
    @classmethod
    def validate_city(cls, v):
        """Valida que la ciudad no esté vacía y no sea solo números."""
        if not v or not v.strip():
            raise ValueError('City cannot be empty')

        v_clean = v.strip().lower()

        # No permitir solo números
        if v_clean.isdigit():
            raise ValueError('City cannot be numeric only')

        # No permitir caracteres especiales peligrosos
        forbidden_chars = [';', "'", '"', '--', '/*', '*/', '\\', '\x00']
        if any(char in v_clean for char in forbidden_chars):
            raise ValueError('City contains invalid characters')

        # Limitar longitud (ya manejado por Field, pero double-check)
        if len(v_clean) > 100:
            raise ValueError('City too long (max 100 characters)')

        return v_clean

    @field_validator('profession')
    @classmethod
    def validate_profession(cls, v):
        """Valida que la profesión sea válida y no contenga código malicioso."""
        if not v or not v.strip():
            raise ValueError('Profession cannot be empty')

        v_clean = v.strip().lower()

        # Caracteres prohibidos (SQL injection prevention)
        forbidden_chars = [';', "'", '"', '--', '/*', '*/', '\\', '\x00', '=', '|']
        if any(char in v_clean for char in forbidden_chars):
            raise ValueError('Profession contains invalid characters')

        # Detectar patrones de inyección SQL
        sql_patterns = [
            r'\b(union|select|insert|update|delete|drop|alter|create|exec)\b',
            r'\b(or|and)\s+\w+\s*[=<>]',
            r'--',
            r'/\*',
            r'\*/',
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v_clean, re.IGNORECASE):
                raise ValueError('Profession contains SQL injection patterns')

        # No permitir solo números
        if v_clean.isdigit():
            raise ValueError('Profession cannot be numeric only')

        # No permitir caracteres no imprimibles
        if any(ord(c) < 32 for c in v_clean if c not in '\n\r\t'):
            raise ValueError('Profession contains invalid characters')

        return v_clean

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        """Valida que el límite esté en un rango seguro."""
        if v < 1:
            raise ValueError('Limit must be at least 1')
        if v > 100:
            raise ValueError('Limit cannot exceed 100 (performance protection)')
        return v


class ServiceSearchValidator(BaseModel):
    """Validator para búsquedas basadas en servicios (V3)."""

    service: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2, max_length=100)
    limit: int = Field(default=20, ge=1, le=100)
    professions: Optional[list[str]] = Field(default=None)

    @field_validator('service')
    @classmethod
    def validate_service(cls, v):
        """Valida el nombre del servicio."""
        if not v or not v.strip():
            raise ValueError('Service cannot be empty')

        v_clean = v.strip().lower()

        # Caracteres prohibidos
        forbidden_chars = [';', "'", '"', '--', '/*', '*/', '\\', '\x00']
        if any(char in v_clean for char in forbidden_chars):
            raise ValueError('Service contains invalid characters')

        return v_clean

    @field_validator('city')
    @classmethod
    def validate_city(cls, v):
        """Valida la ciudad (misma lógica que SearchQueryValidator)."""
        if not v or not v.strip():
            raise ValueError('City cannot be empty')

        v_clean = v.strip().lower()
        forbidden_chars = [';', "'", '"', '--', '/*', '*/', '\\', '\x00']
        if any(char in v_clean for char in forbidden_chars):
            raise ValueError('City contains invalid characters')

        return v_clean

    @field_validator('professions')
    @classmethod
    def validate_professions(cls, v):
        """Valida la lista de profesiones opcionales."""
        if v is None:
            return v

        # Limitar cantidad de profesiones
        if len(v) > 20:
            raise ValueError('Too many professions (max 20)')

        # Validar cada profesión
        for prof in v:
            if not prof or not prof.strip():
                raise ValueError('Profession cannot be empty')

            prof_clean = prof.strip().lower()
            forbidden_chars = [';', "'", '"', '--', '/*', '*/', '\\', '\x00']
            if any(char in prof_clean for char in forbidden_chars):
                raise ValueError(f'Profession "{prof}" contains invalid characters')

        return v


# ============================================================================
# Funciones de sanitización (para uso rápido sin Pydantic)
# ============================================================================

def sanitize_search_input(text: str, max_length: int = 100) -> str:
    """Sanitiza input para prevenir SQL injection.

    Args:
        text: Input a sanitizar
        max_length: Longitud máxima permitida

    Returns:
        Texto sanitizado
    """
    if not text:
        return ""

    # Remover caracteres peligrosos
    text = re.sub(r'[;\'\"\\]', '', text)
    text = text.replace('--', '').replace('/*', '').replace('*/', '')

    # Limitar longitud
    text = text[:max_length]

    # Strip y lowercase
    return text.strip().lower()


def validate_phone_number(phone: str) -> bool:
    """Valida que un número de teléfono sea válido.

    Args:
        phone: Número de teléfono

    Returns:
        True si es válido, False si no
    """
    if not phone:
        return False

    # Remover espacios y caracteres especiales
    phone_clean = re.sub(r'[^\d+]', '', phone)

    # Validar longitud ( Ecuador: +593 xxx xxxx xxx o 0xxx xxx xxx)
    if len(phone_clean) < 10 or len(phone_clean) > 15:
        return False

    # Debe contener solo dígitos y opcionalmente +
    return bool(re.match(r'^\+?\d{10,15}$', phone_clean))
