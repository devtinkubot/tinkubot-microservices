"""Router y utilidades del onboarding de proveedores."""

from .router import (
    es_estado_onboarding,
    manejar_entrada_onboarding,
    manejar_estado_onboarding,
)
from .handlers import (
    manejar_dni_frontal_onboarding,
    manejar_confirmacion_servicios_onboarding,
    manejar_decision_agregar_otro_servicio_onboarding,
    manejar_espera_ciudad_onboarding,
    manejar_espera_red_social_onboarding,
    manejar_espera_real_phone_onboarding,
    manejar_foto_perfil_onboarding,
    mostrar_confirmacion_servicios_onboarding,
)

__all__ = [
    "es_estado_onboarding",
    "manejar_entrada_onboarding",
    "manejar_estado_onboarding",
    "manejar_espera_ciudad_onboarding",
    "manejar_espera_red_social_onboarding",
    "manejar_dni_frontal_onboarding",
    "manejar_foto_perfil_onboarding",
    "manejar_espera_real_phone_onboarding",
    "manejar_confirmacion_servicios_onboarding",
    "manejar_decision_agregar_otro_servicio_onboarding",
    "mostrar_confirmacion_servicios_onboarding",
]
