"""Fachada del flujo conversacional para registro de proveedores.

Este módulo actúa como una fachada que mantiene la compatibilidad con main.py
mientras delega la implementación a módulos especializados.

Módulos especializados:
- validators: Funciones de normalización y validación
- presentation_builders: Constructores de respuestas y menús
- state_handlers: Manejadores de cada estado del flujo
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

# Import de validators (manteniendo nombres originales para compatibilidad)
from flows.validators.normalizar_texto import (
    normalizar_texto as normalize_text,
    parsear_anios_experiencia as parse_experience_years,
)
from flows.validators.validaciones_entrada import (
    parsear_entrada_red_social as parse_social_media_input,
    parsear_cadena_servicios as parse_services_string,
)

# Import de presentation_builders
from flows.presentation_builders.constructor_menu_principal import (
    construir_menu_principal as _build_main_menu,
    construir_respuesta_menu_registro as _build_registration_menu_response,
)
from flows.presentation_builders.constructor_estados_verificacion import (
    construir_respuesta_revision as _build_under_review_response,
    construir_respuesta_verificado as _build_verified_response,
)
from flows.presentation_builders.constructor_consentimiento import (
    construir_notificacion_aprobacion as _build_approval_notification,
    construir_respuesta_consentimiento_aceptado as _build_consent_acknowledged_response,
    construir_respuesta_consentimiento_rechazado as _build_consent_declined_response,
    construir_respuesta_solicitud_consentimiento as _build_consent_prompt_response,
)
from flows.presentation_builders.constructor_servicios import (
    construir_menu_servicios as _build_services_menu,
)
from flows.presentation_builders.constructor_resumen import (
    construir_resumen_confirmacion as _build_confirmation_summary,
)

# Import de state_handlers
from flows.state_handlers.manejar_espera_ciudad import (
    manejar_espera_ciudad as _handle_awaiting_city,
)
from flows.state_handlers.manejar_espera_nombre import (
    manejar_espera_nombre as _handle_awaiting_name,
)
from flows.state_handlers.manejar_espera_profesion import (
    manejar_espera_profesion as _handle_awaiting_profession,
)
from flows.state_handlers.manejar_espera_especialidad import (
    manejar_espera_especialidad as _handle_awaiting_specialty,
)
from flows.state_handlers.manejar_espera_experiencia import (
    manejar_espera_experiencia as _handle_awaiting_experience,
)
from flows.state_handlers.manejar_espera_correo import (
    manejar_espera_correo as _handle_awaiting_email,
)
from flows.state_handlers.manejar_espera_red_social import (
    manejar_espera_red_social as _handle_awaiting_social_media,
)
from flows.state_handlers.manejar_confirmacion import (
    manejar_confirmacion as _handle_confirm,
)


# Re-export de funciones a nivel de módulo para compatibilidad
__all__ = [
    "normalize_text",
    "parse_experience_years",
    "ProviderFlow",
]


class ProviderFlow:
    """Fachada que encapsula toda la lógica del flujo de registro de proveedores.

    Esta clase mantiene la misma interfaz pública que la implementación original,
    delegando en módulos especializados para cada responsabilidad.

    Responsabilidades de los módulos especializados:
    - validators: Validación de inputs de usuario
    - presentation_builders: Construcción de respuestas y mensajes
    - state_handlers: Manejo de estados del flujo conversacional

    Los métodos estáticos 'build_*' construyen respuestas completas
    listas para ser retornadas al cliente HTTP.
    """

    # === Validators (Métodos estáticos directos) ===

    @staticmethod
    def parse_services_string(value: Optional[str]) -> List[str]:
        """Parsea una cadena de servicios separados por delimitadores.

        Delega a: validators.validaciones_entrada.parsear_cadena_servicios
        """
        return parse_services_string(value)

    # === Métodos de presentación (Build Methods) ===

    @staticmethod
    def build_main_menu(is_registered: bool = False) -> str:
        """Construye el menú principal según estado de registro.

        Delega a: presentation_builders.constructor_menu_principal.construir_menu_principal
        """
        return _build_main_menu(is_registered)

    @staticmethod
    def build_registration_menu_response() -> Dict[str, Any]:
        """Construye respuesta completa para menú de registro.

        Delega a: presentation_builders.constructor_menu_principal.construir_respuesta_menu_registro
        """
        return _build_registration_menu_response()

    @staticmethod
    def build_verified_response(has_services: bool) -> Dict[str, Any]:
        """Construye respuesta para proveedor verificado.

        Delega a: presentation_builders.constructor_estados_verificacion.construir_respuesta_verificado
        """
        return _build_verified_response(has_services)

    @staticmethod
    def build_under_review_response() -> Dict[str, Any]:
        """Construye respuesta cuando está en revisión.

        Delega a: presentation_builders.constructor_estados_verificacion.construir_respuesta_revision
        """
        return _build_under_review_response()

    @staticmethod
    def build_approval_notification(provider_name: str = "") -> str:
        """Construye mensaje de notificación de aprobación.

        Delega a: presentation_builders.constructor_consentimiento.construir_notificacion_aprobacion
        """
        return _build_approval_notification(provider_name)

    @staticmethod
    def build_consent_prompt_response() -> Dict[str, Any]:
        """Construye respuesta completa con solicitud de consentimiento.

        Delega a: presentation_builders.constructor_consentimiento.construir_respuesta_solicitud_consentimiento
        """
        return _build_consent_prompt_response()

    @staticmethod
    def build_consent_acknowledged_response(is_registered: bool = False) -> Dict[str, Any]:
        """Construye respuesta cuando el consentimiento es aceptado.

        Delega a: presentation_builders.constructor_consentimiento.construir_respuesta_consentimiento_aceptado
        """
        return _build_consent_acknowledged_response(is_registered)

    @staticmethod
    def build_consent_declined_response() -> Dict[str, Any]:
        """Construye respuesta cuando el consentimiento es rechazado.

        Delega a: presentation_builders.constructor_consentimiento.construir_respuesta_consentimiento_rechazado
        """
        return _build_consent_declined_response()

    @staticmethod
    def build_services_menu(servicios: List[str], max_servicios: int = 5) -> str:
        """Construye menú de gestión de servicios.

        Delega a: presentation_builders.constructor_servicios.construir_menu_servicios
        """
        return _build_services_menu(servicios, max_servicios)

    @staticmethod
    def build_confirmation_summary(flow: Dict[str, Any]) -> str:
        """Construye resumen de confirmación del registro.

        Delega a: presentation_builders.constructor_resumen.construir_resumen_confirmacion
        """
        return _build_confirmation_summary(flow)

    # === State Handlers (Métodos de manejo de estado) ===

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo ciudad.

        Delega a: state_handlers.manejar_espera_ciudad.manejar_espera_ciudad
        """
        return _handle_awaiting_city(flow, message_text)

    @staticmethod
    def handle_awaiting_name(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo nombre.

        Delega a: state_handlers.manejar_espera_nombre.manejar_espera_nombre
        """
        return _handle_awaiting_name(flow, message_text)

    @staticmethod
    def handle_awaiting_profession(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo profesión.

        Delega a: state_handlers.manejar_espera_profesion.manejar_espera_profesion
        """
        return _handle_awaiting_profession(flow, message_text)

    @staticmethod
    def handle_awaiting_specialty(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo especialidad.

        Delega a: state_handlers.manejar_espera_especialidad.manejar_espera_especialidad
        """
        return _handle_awaiting_specialty(flow, message_text)

    @staticmethod
    def handle_awaiting_experience(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo experiencia.

        Delega a: state_handlers.manejar_espera_experiencia.manejar_espera_experiencia
        """
        return _handle_awaiting_experience(flow, message_text)

    @staticmethod
    def handle_awaiting_email(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo correo.

        Delega a: state_handlers.manejar_espera_correo.manejar_espera_correo
        """
        return _handle_awaiting_email(flow, message_text)

    @staticmethod
    def parse_social_media_input(message_text: Optional[str]) -> Dict[str, Optional[str]]:
        """Parsea la entrada de red social y devuelve url + tipo.

        Delega a: validators.validaciones_entrada.parsear_entrada_red_social
        """
        return parse_social_media_input(message_text)

    @staticmethod
    def handle_awaiting_social_media(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """Procesa la entrada del usuario para el campo red social.

        Delega a: state_handlers.manejar_espera_red_social.manejar_espera_red_social
        """
        return _handle_awaiting_social_media(flow, message_text)

    @staticmethod
    async def handle_confirm(
        flow: Dict[str, Any],
        message_text: Optional[str],
        phone: str,
        register_provider_fn: Callable[
            [ProviderCreate], Awaitable[Optional[Dict[str, Any]]]
        ],
        upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
        reset_flow_fn: Callable[[], Awaitable[None]],
        logger: Any,
    ) -> Dict[str, Any]:
        """Procesa la confirmación del registro y crea el proveedor.

        Delega a: state_handlers.manejar_confirmacion.manejar_confirmacion
        """
        return await _handle_confirm(
            flow,
            message_text,
            phone,
            register_provider_fn,
            upload_media_fn,
            reset_flow_fn,
            logger,
        )
