"""Mensajes de confirmación de servicios reutilizados en maintenance."""

from typing import List


def mensaje_confirmacion_servicios(servicios: List[str]) -> str:
    """Genera mensaje de confirmación con los servicios transformados."""
    servicios_formateados = "\n".join([f"• {servicio}" for servicio in servicios])

    return (
        "✨ *He identificado estos servicios:*\n\n"
        f"{servicios_formateados}\n\n"
        "🔍 *Ayudan a que los clientes te encuentren mejor al buscar soluciones.*\n\n"
        "¿Estás de acuerdo con esta lista?\n"
        "*1.* Sí, continuar\n"
        "*2.* No, corregir"
    )


def mensaje_correccion_servicios() -> str:
    """Mensaje cuando el usuario quiere corregir los servicios."""
    return (
        "*Entendido. Escribe tus servicios nuevamente* usando tus propias "
        "palabras e indicando el servicio y la especialidad o área exacta.\n\n"
        "Si vas a escribir más de uno, sepáralos en líneas distintas (ej:\n"
        "asesoría en derecho laboral\n"
        "declaración de impuestos para personas naturales\n"
        "desarrollo de software a medida\n"
        "instalación de cámaras de seguridad\n"
        "terapia psicológica)."
    )


def mensaje_servicios_aceptados() -> str:
    """Mensaje de confirmación cuando el usuario acepta los servicios."""
    return "*¡Perfecto! Servicios confirmados.* Continuemos con tu registro.".strip()


def mensaje_lista_servicios_corregida(servicios: List[str]) -> str:
    """Mensaje confirmando la lista corregida por el usuario."""
    servicios_formateados = "\n".join([f"• {s}" for s in servicios])
    return f"""*✅ Servicios actualizados:*

{servicios_formateados}

Continuemos con tu registro.""".strip()

