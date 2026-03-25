"""Reglas para determinar si un proveedor ya puede operar comercialmente."""

from typing import Iterable, Optional

MINIMO_SERVICIOS_OPERATIVOS = 3

EXPERIENCE_RANGE_UNDER_1 = "Menos de 1 año"
EXPERIENCE_RANGE_1_3 = "1 a 3 años"
EXPERIENCE_RANGE_3_5 = "3 a 5 años"
EXPERIENCE_RANGE_5_10 = "5 a 10 años"
EXPERIENCE_RANGE_10_PLUS = "Más de 10 años"


def normalizar_experiencia(experience_years: Optional[int]) -> int:
    """Convierte la experiencia a entero no negativo."""
    try:
        valor = int(experience_years or 0)
    except (TypeError, ValueError):
        return 0
    return max(valor, 0)


def formatear_rango_experiencia(experience_years: Optional[int]) -> str:
    """Convierte años de experiencia en un rango legible."""
    valor = normalizar_experiencia(experience_years)
    if valor < 1:
        return EXPERIENCE_RANGE_UNDER_1
    if valor < 3:
        return EXPERIENCE_RANGE_1_3
    if valor < 5:
        return EXPERIENCE_RANGE_3_5
    if valor < 10:
        return EXPERIENCE_RANGE_5_10
    return EXPERIENCE_RANGE_10_PLUS


def contar_servicios_validos(servicios: Optional[Iterable[str]]) -> int:
    """Cuenta servicios no vacíos."""
    return sum(1 for servicio in (servicios or []) if str(servicio or "").strip())


def perfil_profesional_completo(
    *,
    experience_years: Optional[int],
    servicios: Optional[Iterable[str]],
) -> bool:
    """Indica si el proveedor ya cumple el mínimo para recibir solicitudes."""
    return (
        normalizar_experiencia(experience_years) > 0
        and contar_servicios_validos(servicios) >= MINIMO_SERVICIOS_OPERATIVOS
    )
