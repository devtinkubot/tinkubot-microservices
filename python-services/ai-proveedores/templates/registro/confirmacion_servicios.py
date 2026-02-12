"""Mensajes de confirmación de servicios transformados."""

from typing import List


def mensaje_confirmacion_servicios(servicios: List[str]) -> str:
    """
    Genera mensaje de confirmación con los servicios transformados.

    Args:
        servicios: Lista de servicios optimizados por OpenAI

    Returns:
        Mensaje formateado con la lista de servicios
    """
    servicios_formateados = "\n".join([f"• {servicio}" for servicio in servicios])

    return f"""✨ *He identificado estos servicios:*

{servicios_formateados}

🔍 *Estos servicios ayudarán a que los clientes te encuentren mejor cuando busquen soluciones.*

¿Estás de acuerdo con esta lista?
*1.* Sí, continuar
*2.* No, corregir""".strip()


def mensaje_correccion_servicios() -> str:
    """
    Mensaje cuando el usuario quiere corregir los servicios.

    Returns:
        Mensaje solicitando corrección manual
    """
    return """*Entendido. Escribe tus servicios nuevamente* usando tus propias palabras.

Sepáralos con comas (ej: reparación de fugas, instalación de tuberías, mantenimiento de desagües).""".strip()


def mensaje_servicios_aceptados() -> str:
    """
    Mensaje de confirmación cuando el usuario acepta los servicios.

    Returns:
        Mensaje de éxito
    """
    return "*¡Perfecto! Servicios confirmados.* Continuemos con tu registro.".strip()


def mensaje_lista_servicios_corregida(servicios: List[str]) -> str:
    """
    Mensaje confirmando la lista corregida por el usuario.

    Args:
        servicios: Lista de servicios corregidos manualmente

    Returns:
        Mensaje de confirmación
    """
    servicios_formateados = "\n".join([f"• {s}" for s in servicios])
    return f"""*✅ Servicios actualizados:*

{servicios_formateados}

Continuemos con tu registro.""".strip()
