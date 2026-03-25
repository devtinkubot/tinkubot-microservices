"""Flujos de mantenimiento del proveedor."""

from .confirmation import manejar_confirmacion
from .deletion import manejar_confirmacion_eliminacion
from .document_update import (
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera_actualizacion,
    manejar_inicio_actualizacion_documentos,
    manejar_inicio_documentos,
)
from .menu import (
    iniciar_flujo_completar_perfil_profesional,
    manejar_estado_menu,
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
)
from .selfie_update import manejar_actualizacion_selfie
from .services import (
    manejar_accion_servicios,
    manejar_accion_servicios_activos,
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
    manejar_eliminar_servicio,
)
from .services_confirmation import (
    manejar_accion_edicion_servicios_registro,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
    manejar_edicion_perfil_profesional,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
    procesar_correccion_manual,
    mostrar_confirmacion_servicios,
)
from .social_update import manejar_actualizacion_redes_sociales
from .specialty import (
    manejar_espera_especialidad,
    normalizar_servicio_registro_individual,
    normalizar_servicios_registro_compartido,
)
from .views import manejar_vista_perfil, render_profile_view
from .wait_certificate import manejar_espera_certificado
from .wait_experience import manejar_espera_experiencia
from .wait_name import manejar_espera_nombre
from .wait_social import manejar_espera_red_social

__all__ = [
    "iniciar_flujo_completar_perfil_profesional",
    "manejar_estado_menu",
    "manejar_submenu_informacion_personal",
    "manejar_submenu_informacion_profesional",
    "manejar_vista_perfil",
    "render_profile_view",
    "manejar_accion_servicios",
    "manejar_accion_servicios_activos",
    "manejar_agregar_servicios",
    "manejar_confirmacion_agregar_servicios",
    "manejar_eliminar_servicio",
    "manejar_confirmacion",
    "manejar_confirmacion_eliminacion",
    "manejar_inicio_documentos",
    "manejar_inicio_actualizacion_documentos",
    "manejar_dni_frontal_actualizacion",
    "manejar_dni_trasera_actualizacion",
    "manejar_actualizacion_selfie",
    "manejar_actualizacion_redes_sociales",
    "manejar_espera_certificado",
    "manejar_espera_experiencia",
    "manejar_espera_especialidad",
    "manejar_espera_nombre",
    "manejar_espera_red_social",
    "manejar_confirmacion_servicio_perfil",
    "manejar_confirmacion_perfil_profesional",
    "manejar_edicion_perfil_profesional",
    "mostrar_confirmacion_servicios",
    "manejar_decision_agregar_otro_servicio",
    "manejar_confirmacion_servicios",
    "manejar_accion_edicion_servicios_registro",
    "manejar_seleccion_reemplazo_servicio_registro",
    "manejar_reemplazo_servicio_registro",
    "manejar_eliminacion_servicio_registro",
    "manejar_agregar_servicio_desde_edicion_registro",
    "procesar_correccion_manual",
    "normalizar_servicio_registro_individual",
    "normalizar_servicios_registro_compartido",
]
