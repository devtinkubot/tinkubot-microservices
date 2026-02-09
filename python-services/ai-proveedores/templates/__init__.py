"""Textos base reutilizables para el servicio de proveedores.

Este módulo centraliza todos los templates de mensajes organizados por dominios de negocio.
"""

# ==================== DOMINIO: INTERFAZ ====================
from templates.interfaz.componentes import pie_instrucciones_respuesta_numerica

# ==================== DOMINIO: CONSENTIMIENTO ====================
from templates.consentimiento import (
    OPCIONES_CONSENTIMIENTO,
    PROMPT_CONSENTIMIENTO,
    BLOQUE_ALCANCE_CONSENTIMIENTO,
    mensaje_consentimiento_aceptado,
    mensaje_consentimiento_rechazado,
    bloque_opciones_consentimiento,
    mensajes_prompt_consentimiento,
)

# ==================== DOMINIO: INTERFAZ - MENÚS ====================
from templates.interfaz import (
    MENU_PRINCIPAL_PROVEEDOR,
    MENU_POST_REGISTRO_PROVEEDOR,
    mensaje_menu_principal_proveedor,
    mensaje_menu_post_registro_proveedor,
    mensaje_menu_servicios_proveedor,
    informar_cierre_sesion,
    error_opcion_no_reconocida,
    solicitar_selfie_actualizacion,
    solicitar_selfie_requerida,
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_red_social_actualizacion,
    error_actualizar_redes_sociales,
    confirmar_actualizacion_redes_sociales,
    error_limite_servicios_alcanzado,
    preguntar_nuevo_servicio,
    error_servicio_no_interpretado,
    error_guardar_servicio,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_servicio_eliminar,
    error_eliminar_servicio,
    confirmar_servicio_eliminado,
)

# ==================== DOMINIO: REGISTRO ====================
from templates.registro import (
    MENSAJE_GUIA,
    PROMPT_INICIO_REGISTRO,
    mensaje_guia_proveedor,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
    preguntar_nombre,
    preguntar_real_phone,
    error_real_phone_invalido,
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
    informar_datos_recibidos,
)

# ==================== DOMINIO: SESIÓN ====================
from templates.sesion import (
    informar_reinicio_conversacion,
    informar_reinicio_con_eliminacion,
    informar_timeout_inactividad,
    informar_reinicio_completo,
)

# ==================== DOMINIO: VERIFICACIÓN ====================
from templates.verificacion import (
    mensaje_proveedor_en_revision,
    mensaje_proveedor_verificado,
)

# Compatibilidad con prompts.py - re-exportar con nombres originales
PIE_CONSENTIMIENTO = pie_instrucciones_respuesta_numerica
MENSAJE_CONSENTIMIENTO_RECHAZADO = (
    "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
    'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
    "Gracias por tu tiempo."
)

__all__ = [
    # Comunes
    "pie_instrucciones_respuesta_numerica",
    "PIE_CONSENTIMIENTO",
    # Consentimiento
    "PROMPT_CONSENTIMIENTO",
    "BLOQUE_ALCANCE_CONSENTIMIENTO",
    "OPCIONES_CONSENTIMIENTO",
    "bloque_opciones_consentimiento",
    "mensajes_prompt_consentimiento",
    "mensaje_consentimiento_aceptado",
    "mensaje_consentimiento_rechazado",
    # Registro
    "PROMPT_INICIO_REGISTRO",
    "MENSAJE_GUIA",
    "mensaje_guia_proveedor",
    "preguntar_correo_opcional",
    "preguntar_actualizar_ciudad",
    "preguntar_nombre",
    "preguntar_real_phone",
    "error_real_phone_invalido",
    "solicitar_foto_dni_frontal",
    "solicitar_foto_dni_trasera",
    "solicitar_foto_dni_trasera_requerida",
    "solicitar_selfie_registro",
    "solicitar_selfie_requerida_registro",
    "informar_datos_recibidos",
    # Menús
    "MENU_PRINCIPAL_PROVEEDOR",
    "MENU_POST_REGISTRO_PROVEEDOR",
    "mensaje_menu_principal_proveedor",
    "mensaje_menu_post_registro_proveedor",
    "mensaje_menu_servicios_proveedor",
    # Interfaz - mensajes comunes
    "informar_cierre_sesion",
    "error_opcion_no_reconocida",
    # Interfaz - actualización de perfil
    "solicitar_selfie_actualizacion",
    "solicitar_selfie_requerida",
    "confirmar_selfie_actualizada",
    "error_actualizar_selfie",
    "solicitar_red_social_actualizacion",
    "error_actualizar_redes_sociales",
    "confirmar_actualizacion_redes_sociales",
    # Interfaz - servicios
    "error_limite_servicios_alcanzado",
    "preguntar_nuevo_servicio",
    "error_servicio_no_interpretado",
    "error_guardar_servicio",
    "confirmar_servicios_agregados",
    "informar_limite_servicios_alcanzado",
    "informar_sin_servicios_eliminar",
    "preguntar_servicio_eliminar",
    "error_eliminar_servicio",
    "confirmar_servicio_eliminado",
    # Verificación
    "mensaje_proveedor_en_revision",
    "mensaje_proveedor_verificado",
    # Sesión
    "informar_reinicio_conversacion",
    "informar_reinicio_con_eliminacion",
    "informar_timeout_inactividad",
    "informar_reinicio_completo",
]
