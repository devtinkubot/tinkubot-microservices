"""Mensajes para captura incremental de servicios durante el registro."""

from typing import List


def preguntar_servicios_registro() -> str:
    """Solicita el primer servicio del proveedor."""
    return (
        "*Escribe tu primer servicio* e indica el servicio y la especialidad o "
        "área exacta.\n"
        "Ejemplos: asesoría en ley laboral, defensa en demandas laborales, "
        "asesoría por acoso laboral, destape de cañerías, reparación de fugas, "
        "desarrollo web."
    )


def preguntar_siguiente_servicio_registro(
    indice: int,
    maximo: int,
    total_requerido: int | None = None,
) -> str:
    """Solicita el siguiente servicio del proveedor."""
    if total_requerido:
        progreso = min(indice, total_requerido)
        ejemplos_por_paso = {
            1: (
                "Ejemplo para plomero o abogado:\n"
                "*destape de cañerías*, *representación legal en materia laboral*."
            ),
            2: (
                "Ejemplo para contador o jardinero:\n"
                "*declaración de impuestos para personas naturales*, "
                "*mantenimiento de jardines residenciales*."
            ),
            3: (
                "Ejemplo para electricista o arquitecto:\n"
                "*instalación de tableros eléctricos*, "
                "*diseño de planos arquitectónicos*."
            ),
        }
        return (
            f"*{progreso}/{total_requerido}:* Escribe un *servicio o habilidad* que ofreces, "
            "debes especificar la *especialidad* o *área exacta*.\n"
            + ejemplos_por_paso.get(
                progreso,
                ejemplos_por_paso[1],
            )
        )
    return (
        f"*Escribe el servicio {indice} de {maximo}* indicando el servicio y la "
        "especialidad o área exacta."
    )


def confirmar_servicio_y_preguntar_otro(
    servicio: str,
    cantidad_actual: int,
    maximo: int,
) -> str:
    """Confirma un servicio válido y pregunta si desea agregar otro."""
    return (
        f"Servicio {cantidad_actual} de {maximo} registrado: *{servicio}*.\n\n"
        "¿Quieres agregar otro servicio?\n"
        "*1.* Sí, agregar otro\n"
        "*2.* No, continuar"
    )


def mensaje_resumen_servicios_registro(servicios: List[str], maximo: int) -> str:
    """Muestra el resumen final de servicios capturados."""
    servicios_formateados = "\n".join(
        [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
    )
    return (
        f"*Resumen de servicios principales ({len(servicios)}/{maximo}):*\n\n"
        f"{servicios_formateados}\n\n"
        "¿Estás de acuerdo con esta lista?\n"
        "*1.* Sí, continuar\n"
        "*2.* No, corregir"
    )


def mensaje_menu_edicion_servicios_registro(
    servicios: List[str],
    maximo: int,
) -> str:
    """Muestra acciones de corrección sobre la lista temporal."""
    servicios_formateados = "\n".join(
        [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
    )
    return (
        f"*Servicios principales capturados ({len(servicios)}/{maximo}):*\n\n"
        f"{servicios_formateados}\n\n"
        "¿Qué deseas corregir?\n"
        "*1.* Reemplazar un servicio\n"
        "*2.* Eliminar un servicio\n"
        "*3.* Agregar otro servicio\n"
        "*4.* Volver al resumen"
    )


def preguntar_numero_servicio_reemplazar() -> str:
    return "Escribe el número del servicio que deseas reemplazar."


def preguntar_numero_servicio_eliminar() -> str:
    return "Escribe el número del servicio que deseas eliminar."


def preguntar_nuevo_servicio_reemplazo(numero: int, actual: str) -> str:
    return (
        f"Escribe el nuevo texto para el servicio {numero} "
        f'("*{actual}*"), indicando el servicio y la especialidad o área exacta.'
    )


def mensaje_servicio_actualizado(servicio: str) -> str:
    return f"Servicio actualizado: *{servicio}*."


def mensaje_servicio_eliminado_registro(servicio: str) -> str:
    return f"Servicio eliminado de la lista: *{servicio}*."


def mensaje_servicio_duplicado_registro(servicio: str) -> str:
    return f"El servicio *{servicio}* ya está en tu lista. " "Escribe otro diferente."


def mensaje_maximo_servicios_registro(maximo: int) -> str:
    return (
        f"Ya completaste tus {maximo} servicios principales para esta revisión. "
        "Revisemos la lista final."
    )


def mensaje_debes_registrar_al_menos_un_servicio() -> str:
    return "Debes registrar al menos un servicio para continuar."


def mensaje_debes_registrar_mas_servicios(minimo: int) -> str:
    return f"Necesitas registrar al menos *{minimo} servicios* para completar tu perfil profesional."


def mensaje_error_opcion_agregar_otro() -> str:
    return (
        "Responde *1* para agregar otro servicio o *2* para continuar con el "
        "resumen."
    )


def mensaje_error_opcion_edicion_servicios() -> str:
    return "Responde con una opción válida del 1 al 4."
