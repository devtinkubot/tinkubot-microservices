"""Módulo de gestores de estado para el flujo de proveedores."""

from .gestor_actualizacion_redes import manejar_actualizacion_redes_sociales
from .gestor_actualizacion_selfie import manejar_actualizacion_selfie
from .gestor_confirmacion import manejar_confirmacion

# Confirmación de servicios (nuevo)
from .gestor_confirmacion_servicios import (
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
    mostrar_confirmacion_servicios,
    procesar_correccion_manual,
)
from .gestor_consentimiento import manejar_estado_consentimiento
from .gestor_documentos import (
    manejar_dni_frontal,
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera,
    manejar_dni_trasera_actualizacion,
    manejar_inicio_actualizacion_documentos,
    manejar_inicio_documentos,
    manejar_selfie_registro,
)
from .gestor_eliminacion import manejar_confirmacion_eliminacion
from .gestor_espera_ciudad import manejar_espera_ciudad
from .gestor_espera_certificado import manejar_espera_certificado
from .gestor_espera_correo import manejar_espera_correo
from .gestor_espera_especialidad import manejar_espera_especialidad
from .gestor_espera_experiencia import manejar_espera_experiencia
from .gestor_espera_nombre import manejar_espera_nombre

# Nuevo: captura de real_phone para @lid
from .gestor_espera_real_phone import manejar_espera_real_phone

# Fase 4: Eliminada referencia a awaiting_profession
from .gestor_espera_red_social import manejar_espera_red_social
from .gestor_menu import (
    iniciar_flujo_completar_perfil_profesional,
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
    manejar_estado_menu,
)
from .gestor_servicios import (
    manejar_accion_servicios,
    manejar_accion_servicios_activos,
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
    manejar_eliminar_servicio,
)

__all__ = [
    "manejar_confirmacion",
    "manejar_estado_consentimiento",
    "manejar_estado_menu",
    "manejar_submenu_informacion_personal",
    "manejar_submenu_informacion_profesional",
    "manejar_actualizacion_redes_sociales",
    "manejar_accion_servicios",
    "manejar_accion_servicios_activos",
    "manejar_agregar_servicios",
    "manejar_confirmacion_agregar_servicios",
    "manejar_eliminar_servicio",
    "manejar_actualizacion_selfie",
    "manejar_confirmacion_eliminacion",
    "manejar_inicio_documentos",
    "manejar_inicio_actualizacion_documentos",
    "manejar_dni_frontal",
    "manejar_dni_frontal_actualizacion",
    "manejar_dni_trasera",
    "manejar_dni_trasera_actualizacion",
    "manejar_selfie_registro",
    "manejar_espera_ciudad",
    "manejar_espera_certificado",
    "manejar_espera_correo",
    "manejar_espera_especialidad",
    "manejar_espera_experiencia",
    "manejar_espera_nombre",
    "manejar_espera_real_phone",
    # Fase 4: Eliminada referencia a awaiting_profession
    "manejar_espera_red_social",
    "iniciar_flujo_completar_perfil_profesional",
    # Confirmación de servicios (nuevo)
    "manejar_accion_edicion_servicios_registro",
    "manejar_agregar_servicio_desde_edicion_registro",
    "manejar_confirmacion_perfil_profesional",
    "manejar_confirmacion_servicio_perfil",
    "manejar_confirmacion_servicios",
    "manejar_decision_agregar_otro_servicio",
    "manejar_edicion_perfil_profesional",
    "manejar_eliminacion_servicio_registro",
    "manejar_reemplazo_servicio_registro",
    "manejar_seleccion_reemplazo_servicio_registro",
    "mostrar_confirmacion_servicios",
    "procesar_correccion_manual",
]
