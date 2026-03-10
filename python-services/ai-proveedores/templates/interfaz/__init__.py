"""Mensajes relacionados con menús y componentes de interfaz."""

from .actualizacion_perfil import (
    confirmar_actualizacion_redes_sociales,
    confirmar_documentos_actualizados,
    confirmar_selfie_actualizada,
    error_actualizar_documentos,
    error_actualizar_redes_sociales,
    error_actualizar_selfie,
    solicitar_dni_actualizacion,
    solicitar_red_social_actualizacion,
    solicitar_selfie_actualizacion,
    solicitar_selfie_requerida,
)
from .componentes import pie_instrucciones_respuesta_numerica
from .eliminacion_registro import (
    advertencia_eliminacion_irreversible,
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
    solicitar_confirmacion_eliminacion,
)
from .mensajes_comunes import (
    error_opcion_no_reconocida,
    informar_cierre_sesion,
)
from .mensajes_servicios import (
    confirmar_servicio_eliminado,
    confirmar_servicios_agregados,
    error_eliminar_servicio,
    error_guardar_servicio,
    error_limite_servicios_alcanzado,
    error_normalizar_servicio,
    error_servicio_no_interpretado,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    mensaje_confirmacion_servicios_menu,
    mensaje_correccion_servicios_menu,
    preguntar_nuevo_servicio,
    preguntar_servicio_eliminar,
)
from .menus import (
    MENU_POST_REGISTRO_PROVEEDOR,
    MENU_PRINCIPAL_PROVEEDOR,
    mensaje_menu_post_registro_proveedor,
    mensaje_menu_principal_proveedor,
    mensaje_menu_servicios_proveedor,
)

__all__ = [
    # Menús
    "MENU_PRINCIPAL_PROVEEDOR",
    "MENU_POST_REGISTRO_PROVEEDOR",
    "mensaje_menu_principal_proveedor",
    "mensaje_menu_post_registro_proveedor",
    "mensaje_menu_servicios_proveedor",
    # Componentes
    "pie_instrucciones_respuesta_numerica",
    # Mensajes comunes
    "informar_cierre_sesion",
    "error_opcion_no_reconocida",
    # Actualización de perfil
    "solicitar_selfie_actualizacion",
    "solicitar_selfie_requerida",
    "confirmar_selfie_actualizada",
    "error_actualizar_selfie",
    "solicitar_dni_actualizacion",
    "confirmar_documentos_actualizados",
    "error_actualizar_documentos",
    "solicitar_red_social_actualizacion",
    "error_actualizar_redes_sociales",
    "confirmar_actualizacion_redes_sociales",
    # Servicios
    "error_limite_servicios_alcanzado",
    "preguntar_nuevo_servicio",
    "error_servicio_no_interpretado",
    "error_guardar_servicio",
    "error_normalizar_servicio",
    "mensaje_confirmacion_servicios_menu",
    "mensaje_correccion_servicios_menu",
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
