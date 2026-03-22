"""Reglas para determinar si un proveedor ya puede operar comercialmente."""

from typing import Iterable, Optional

MINIMO_SERVICIOS_OPERATIVOS = 3


def normalizar_experiencia(experience_years: Optional[int]) -> int:
    """Convierte la experiencia a entero no negativo."""
    try:
        valor = int(experience_years or 0)
    except (TypeError, ValueError):
        return 0
    return max(valor, 0)


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
