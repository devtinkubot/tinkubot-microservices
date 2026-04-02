"""Reglas locales de estado operativo para onboarding."""

from typing import Iterable, Optional

MINIMO_SERVICIOS_OPERATIVOS = 1

EXPERIENCE_RANGE_UNDER_1 = "Menos de 1 año"
EXPERIENCE_RANGE_1_3 = "1 a 3 años"
EXPERIENCE_RANGE_3_5 = "3 a 5 años"
EXPERIENCE_RANGE_5_10 = "5 a 10 años"
EXPERIENCE_RANGE_10_PLUS = "Más de 10 años"


def normalizar_experiencia(experience_value: Optional[int]) -> int:
    try:
        valor = int(experience_value or 0)
    except (TypeError, ValueError):
        return 0
    return max(valor, 0)


def formatear_rango_experiencia(experience_value: Optional[int]) -> str:
    valor = normalizar_experiencia(experience_value)
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
    return sum(1 for servicio in (servicios or []) if str(servicio or "").strip())


def perfil_profesional_completo(
    *,
    experience_range: Optional[str],
    servicios: Optional[Iterable[str]],
) -> bool:
    return (
        bool(str(experience_range or "").strip())
        and contar_servicios_validos(servicios) >= MINIMO_SERVICIOS_OPERATIVOS
    )
