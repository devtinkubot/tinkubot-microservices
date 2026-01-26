"""Mensajes relacionados con menús y componentes de interfaz."""

from .menus import (
    PROVIDER_MAIN_MENU,
    PROVIDER_POST_REGISTRATION_MENU,
    provider_main_menu_message,
    provider_post_registration_menu_message,
    provider_services_menu_message,
)

from .componentes import pie_instrucciones_respuesta_numerica

from .mensajes_comunes import (
    informar_cierre_session,
    error_opcion_no_reconocida,
)

from .actualizacion_perfil import (
    solicitar_selfie_actualizacion,
    solicitar_selfie_requerida,
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_red_social_actualizacion,
    error_actualizar_redes_sociales,
    confirmar_actualizacion_redes_sociales,
)

from .mensajes_servicios import (
    error_limite_servicios_alcanzado,
    preguntar_nuevo_servicio,
    error_servicio_no_interpretado,
    error_servicios_ya_registrados,
    error_guardar_servicio,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_servicio_eliminar,
    error_eliminar_servicio,
    confirmar_servicio_eliminado,
)

from .eliminacion_registro import (
    solicitar_confirmacion_eliminacion,
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
    advertencia_eliminacion_irreversible,
)

__all__ = [
    # Menús
    "PROVIDER_MAIN_MENU",
    "PROVIDER_POST_REGISTRATION_MENU",
    "provider_main_menu_message",
    "provider_post_registration_menu_message",
    "provider_services_menu_message",
    # Componentes
    "pie_instrucciones_respuesta_numerica",
    # Mensajes comunes
    "informar_cierre_session",
    "error_opcion_no_reconocida",
    # Actualización de perfil
    "solicitar_selfie_actualizacion",
    "solicitar_selfie_requerida",
    "confirmar_selfie_actualizada",
    "error_actualizar_selfie",
    "solicitar_red_social_actualizacion",
    "error_actualizar_redes_sociales",
    "confirmar_actualizacion_redes_sociales",
    # Servicios
    "error_limite_servicios_alcanzado",
    "preguntar_nuevo_servicio",
    "error_servicio_no_interpretado",
    "error_servicios_ya_registrados",
    "error_guardar_servicio",
    "confirmar_servicios_agregados",
    "informar_limite_servicios_alcanzado",
    "informar_sin_servicios_eliminar",
    "preguntar_servicio_eliminar",
    "error_eliminar_servicio",
    "confirmar_servicio_eliminado",
    # Eliminación de registro
    "solicitar_confirmacion_eliminacion",
    "confirmar_eliminacion_exitosa",
    "error_eliminacion_fallida",
    "informar_eliminacion_cancelada",
    "advertencia_eliminacion_irreversible",
]
