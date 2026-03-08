"""Mensajes relacionados con el flujo de registro de proveedores."""

from .pasos_registro import (
    PROMPT_INICIO_REGISTRO,
    MENSAJE_GUIA,
    mensaje_guia_proveedor,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
    preguntar_nombre,
    preguntar_real_phone,
    error_real_phone_invalido,
)

from .documentacion import (
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)

from .confirmacion import (
    informar_datos_recibidos,
    pedir_confirmacion_resumen,
)

from .confirmacion_servicios import (
    mensaje_confirmacion_servicios,
    mensaje_correccion_servicios,
    mensaje_servicios_aceptados,
    mensaje_lista_servicios_corregida,
)

from .validacion_ciudad import (
    preguntar_ciudad,
    error_ciudad_corta,
    error_ciudad_larga,
    error_ciudad_caracteres_invalidos,
    error_ciudad_multiple,
    error_ciudad_frase,
    error_ciudad_no_reconocida,
)
from .ubicacion import (
    solicitar_ciudad_registro,
    solicitar_ciudad_actualizacion,
    ui_solicitud_ubicacion,
    mensaje_error_resolviendo_ubicacion,
)

__all__ = [
    # Pasos de registro
    "PROMPT_INICIO_REGISTRO",
    "MENSAJE_GUIA",
    "mensaje_guia_proveedor",
    "preguntar_correo_opcional",
    "preguntar_actualizar_ciudad",
    "preguntar_nombre",
    "preguntar_real_phone",
    "error_real_phone_invalido",
    # Documentación
    "solicitar_foto_dni_frontal",
    "solicitar_foto_dni_trasera",
    "solicitar_foto_dni_trasera_requerida",
    "solicitar_selfie_registro",
    "solicitar_selfie_requerida_registro",
    # Confirmación
    "informar_datos_recibidos",
    "pedir_confirmacion_resumen",
    # Confirmación de servicios
    "mensaje_confirmacion_servicios",
    "mensaje_correccion_servicios",
    "mensaje_servicios_aceptados",
    "mensaje_lista_servicios_corregida",
    # Validación de ciudad
    "preguntar_ciudad",
    "error_ciudad_corta",
    "error_ciudad_larga",
    "error_ciudad_caracteres_invalidos",
    "error_ciudad_multiple",
    "error_ciudad_frase",
    "error_ciudad_no_reconocida",
    "solicitar_ciudad_registro",
    "solicitar_ciudad_actualizacion",
    "ui_solicitud_ubicacion",
    "mensaje_error_resolviendo_ubicacion",
]
