"""Compatibilidad histórica con el router canónico de onboarding."""

from routes.onboarding.router import es_estado_onboarding, manejar_estado_onboarding
from services.onboarding.ciudad import manejar_espera_ciudad_onboarding
from services.onboarding.consentimiento import (
    manejar_estado_consentimiento_onboarding,
)
from services.onboarding.documentos import (
    manejar_dni_frontal_onboarding,
    manejar_foto_perfil_onboarding,
)
from services.onboarding.experiencia import (
    manejar_espera_experiencia_onboarding,
)
from services.onboarding.real_phone import (
    manejar_espera_real_phone_onboarding,
)
from services.onboarding.redes_sociales import (
    manejar_espera_red_social_onboarding,
)
from services.onboarding.servicios import (
    manejar_espera_servicios_onboarding,
)
from flows.onboarding.handlers.servicios_confirmacion import (
    manejar_decision_agregar_otro_servicio_onboarding,
)

__all__ = [
    "es_estado_onboarding",
    "manejar_estado_onboarding",
    "manejar_espera_ciudad_onboarding",
    "manejar_espera_red_social_onboarding",
    "manejar_dni_frontal_onboarding",
    "manejar_foto_perfil_onboarding",
    "manejar_espera_real_phone_onboarding",
    "manejar_espera_experiencia_onboarding",
    "manejar_espera_servicios_onboarding",
    "manejar_estado_consentimiento_onboarding",
    "manejar_decision_agregar_otro_servicio_onboarding",
]
