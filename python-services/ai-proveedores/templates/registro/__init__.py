"""Mensajes relacionados con el flujo de registro de proveedores."""

from .pasos_registro import (
    PROMPT_INICIO_REGISTRO,
    MENSAJE_GUIA,
    mensaje_guia_proveedor,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
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
)

__all__ = [
    # Pasos de registro
    "PROMPT_INICIO_REGISTRO",
    "MENSAJE_GUIA",
    "mensaje_guia_proveedor",
    "preguntar_correo_opcional",
    "preguntar_actualizar_ciudad",
    # Documentación
    "solicitar_foto_dni_frontal",
    "solicitar_foto_dni_trasera",
    "solicitar_foto_dni_trasera_requerida",
    "solicitar_selfie_registro",
    "solicitar_selfie_requerida_registro",
    # Confirmación
    "informar_datos_recibidos",
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
]
