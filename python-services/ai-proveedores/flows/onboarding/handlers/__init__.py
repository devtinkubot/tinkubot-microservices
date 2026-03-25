"""Handlers del onboarding de proveedores."""

from .ciudad import manejar_espera_ciudad_onboarding
from .consentimiento import manejar_estado_consentimiento_onboarding
from .documentos import (
    manejar_dni_frontal_onboarding,
    manejar_foto_perfil_onboarding,
)
from .experiencia import manejar_espera_experiencia_onboarding
from .real_phone import manejar_espera_real_phone_onboarding
from .redes_sociales import manejar_espera_red_social_onboarding
from .servicios import manejar_espera_servicios_onboarding
from .servicios_confirmacion import (
    manejar_confirmacion_servicios_onboarding,
    manejar_decision_agregar_otro_servicio_onboarding,
)

__all__ = [
    "manejar_espera_ciudad_onboarding",
    "manejar_estado_consentimiento_onboarding",
    "manejar_dni_frontal_onboarding",
    "manejar_foto_perfil_onboarding",
    "manejar_espera_experiencia_onboarding",
    "manejar_espera_red_social_onboarding",
    "manejar_espera_real_phone_onboarding",
    "manejar_espera_servicios_onboarding",
    "manejar_confirmacion_servicios_onboarding",
    "manejar_decision_agregar_otro_servicio_onboarding",
]
