"""Mensajes transversales para interacción y fallbacks de flujo."""


def mensaje_reiniciar_ciudad_principal() -> str:
    return "Reiniciemos. *En que ciudad trabajas principalmente?*"


def mensaje_elige_opcion_interes() -> str:
    return "Elige la opción de interés."


def mensaje_preguntar_servicio_registrado() -> str:
    return (
        "*Escribe el servicio que estás registrando*\n\n"
        "Envía un solo servicio por mensaje y agrega la especialidad o área "
        "si aplica."
    )


def mensaje_formato_usuario_red_social() -> str:
    return "Envíame el usuario como *usuario*, *@usuario* o URL completa."


def mensaje_formato_usuario_facebook() -> str:
    return "Envíame tu usuario de *Facebook* como *usuario*, *@usuario* o URL completa."


def mensaje_formato_usuario_instagram() -> str:
    return "Envíame tu usuario de *Instagram* como *usuario*, *@usuario* o URL completa."


def mensaje_elige_red_social() -> str:
    return "Primero elige si deseas agregar *Facebook* o *Instagram*."


def mensaje_validacion_identidad_cedula() -> str:
    return (
        "*Para validar tu identidad y mantener la confianza en la "
        "plataforma*, necesito una foto clara de la parte frontal de "
        "tu cédula. *Envíala como imagen adjunta.*"
    )


def mensaje_nombre_completo_requerido() -> str:
    return "*Necesito tu nombre y apellido completos.* Ejemplo: Juan Pérez."


def mensaje_nombre_caracteres_validos() -> str:
    return (
        "*El nombre solo debe contener letras, espacios y guiones.* "
        "Ejemplo: Juan Pérez."
    )


def mensaje_nombre_completo_solicitado() -> str:
    return "*Por favor, escribe tu nombre completo.* Ejemplo: Juan Pérez."


def mensaje_no_pude_validar_datos_registro(mensaje_error: str) -> str:
    return (
        f"*No pude validar tus datos:* {mensaje_error}. "
        "Revisá que nombre y ciudad cumplan con el formato."
    )


def mensaje_no_pude_guardar_informacion_registro() -> str:
    return "*Hubo un error al guardar tu informacion. Por favor intenta de nuevo.*"


def mensaje_no_entendi_respuesta() -> str:
    return "*No entendí tu respuesta.*"


def mensaje_servicio_obligatorio() -> str:
    return (
        "*Los servicios son obligatorios.* "
        "Escribe un servicio indicando el servicio y la especialidad o área "
        "exacta."
    )


def mensaje_servicio_minimo_caracteres() -> str:
    return "*El servicio debe tener al menos 2 caracteres.* Escribelo con más detalle."


def mensaje_servicio_maximo_caracteres() -> str:
    return (
        "*El texto es muy largo (máx. 300 caracteres).* "
        "Envía una versión más corta del servicio."
    )


def mensaje_no_pude_procesar_servicios() -> str:
    return (
        "*No pude procesar tus servicios en este momento.* "
        "Por favor intenta nuevamente en unos minutos."
    )


def mensaje_tuvimos_problema_normalizar_servicio() -> str:
    return "*Tuvimos un problema al normalizar tu servicio.*"


def mensaje_no_pude_interpretar_servicio() -> str:
    return (
        "*No pude interpretar ese servicio.* "
        "Por favor reescribelo de forma más simple y específica."
    )


def mensaje_no_pude_interpretar_servicio_especifico() -> str:
    return (
        "No pude interpretar ese servicio. "
        "Escribe una versión más específica."
    )


def mensaje_formato_servicios_compartido() -> str:
    return (
        "Escribe el servicio con el mayor detalle posible. "
        "Si necesitas, sepáralo por coma o en una línea distinta."
    )


def mensaje_ya_tenias_esos_servicios() -> str:
    return (
        "Ya tenías esos servicios en tu lista. "
        "Escribe otros distintos en la misma línea."
    )


def mensaje_tomamos_solo_primeros_servicios(maximo: int) -> str:
    return (
        f"Tomé solo los primeros {maximo} servicios "
        "porque ese es el máximo permitido."
    )


def mensaje_indica_servicio_exacto() -> str:
    return (
        "Indica el servicio o especialidad exacta que ofreces."
    )


def mensaje_reescribir_mas_especifico() -> str:
    return "Escribe una versión más específica."


def mensaje_no_ubicar_paso_actual() -> str:
    return (
        "No pude ubicar tu paso actual. Escribe *menu* para seguir "
        "o *registro* si deseas reiniciar."
    )


def mensaje_proceso_registro_activo() -> str:
    return "Tu proceso de registro sigue activo. Responde para continuar donde te quedaste."


def mensaje_enviar_certificado_o_omitir() -> str:
    return "Envíame el certificado como imagen o toca *Omitir* para continuar."


def mensaje_no_pude_identificar_perfil_certificado() -> str:
    return (
        "No pude identificar tu perfil para guardar el certificado. "
        "Intenta de nuevo."
    )


def mensaje_no_pude_procesar_imagen_certificado() -> str:
    return "No pude procesar esa imagen. Envíala de nuevo o toca *Omitir*."


def mensaje_no_pude_guardar_certificado() -> str:
    return (
        "No pude guardar ese certificado en este momento. "
        "Intenta nuevamente o toca *Omitir*."
    )


def mensaje_no_pude_identificar_certificado_reemplazo() -> str:
    return "No pude identificar el certificado a reemplazar. Intenta nuevamente."


def mensaje_certificado_actualizado_exitosamente() -> str:
    return "✅ Tu certificado activo fue actualizado correctamente."


def mensaje_certificado_agregado_exitosamente() -> str:
    return "✅ Tu certificado fue agregado correctamente."


def mensaje_certificado_actualizado() -> str:
    return "✅ Tu certificado fue actualizado correctamente."


def mensaje_perfecto_guardar_perfil_profesional() -> str:
    return "✅ Perfecto. Voy a guardar tu perfil profesional."


def mensaje_datos_registro() -> str:
    return "*Datos de registro*"


def descripcion_foto_perfil_actual() -> str:
    return "Esta es tu foto de perfil actual."


def descripcion_cedula_frontal_actual() -> str:
    return "Esta es la foto frontal de tu cédula."


def descripcion_cedula_reverso_actual() -> str:
    return "Esta es la foto reverso de tu cédula."
