"""Mensajes relacionados con el flujo de registro de proveedores."""

from .confirmacion import (
    informar_datos_recibidos,
    pedir_confirmacion_resumen,
)
from .confirmacion_servicios import (
    mensaje_confirmacion_servicios,
    mensaje_correccion_servicios,
    mensaje_lista_servicios_corregida,
    mensaje_servicios_aceptados,
)
from .documentacion import (
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)
from .pasos_registro import (
    MENSAJE_GUIA,
    PROMPT_INICIO_REGISTRO,
    error_real_phone_invalido,
    mensaje_guia_proveedor,
    preguntar_actualizar_ciudad,
    preguntar_correo_opcional,
    preguntar_nombre,
    preguntar_real_phone,
)
from .servicios import (
    confirmar_servicio_y_preguntar_otro,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_error_opcion_agregar_otro,
    mensaje_error_opcion_edicion_servicios,
    mensaje_maximo_servicios_registro,
    mensaje_menu_edicion_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_actualizado,
    mensaje_servicio_duplicado_registro,
    mensaje_servicio_eliminado_registro,
    preguntar_nuevo_servicio_reemplazo,
    preguntar_numero_servicio_eliminar,
    preguntar_numero_servicio_reemplazar,
    preguntar_servicios_registro,
    preguntar_siguiente_servicio_registro,
)
from .ubicacion import (
    mensaje_error_resolviendo_ubicacion,
    solicitar_ciudad_actualizacion,
    solicitar_ciudad_registro,
    ui_solicitud_ubicacion,
)
from .validacion_ciudad import (
    error_ciudad_caracteres_invalidos,
    error_ciudad_corta,
    error_ciudad_frase,
    error_ciudad_larga,
    error_ciudad_multiple,
    error_ciudad_no_reconocida,
    preguntar_ciudad,
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
    "preguntar_servicios_registro",
    "preguntar_siguiente_servicio_registro",
    "confirmar_servicio_y_preguntar_otro",
    "mensaje_resumen_servicios_registro",
    "mensaje_menu_edicion_servicios_registro",
    "preguntar_numero_servicio_reemplazar",
    "preguntar_numero_servicio_eliminar",
    "preguntar_nuevo_servicio_reemplazo",
    "mensaje_servicio_actualizado",
    "mensaje_servicio_eliminado_registro",
    "mensaje_servicio_duplicado_registro",
    "mensaje_maximo_servicios_registro",
    "mensaje_debes_registrar_al_menos_un_servicio",
    "mensaje_error_opcion_agregar_otro",
    "mensaje_error_opcion_edicion_servicios",
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
