"""Mensajes relacionados con estados de verificación de proveedores."""

# ==================== FUNCIONES ====================


def mensaje_proveedor_en_revision(nombre: str) -> str:
    """Mensaje cuando el perfil está en revisión.

    Args:
        nombre: Nombre del proveedor para personalizar el mensaje.
    """
    return (
        "✅ *Valoramos tu confianza en TinkuBot.* "
        "Tu perfil ya fue registrado y nuestro equipo lo está revisando; "
        "si necesitamos algo adicional, te escribimos."
    )


def mensaje_proveedor_verificado() -> str:
    """Mensaje cuando el perfil ha sido verificado exitosamente."""
    return (
        "✅ Tu perfil profesional fue aprobado. "
        "Ya puedes gestionar tu perfil y atender solicitudes de clientes."
    )


def mensaje_perfil_profesional_en_revision() -> str:
    """Mensaje cuando el perfil profesional ya fue enviado a revisión humana."""
    return (
        "✅ *Gracias por completar tu perfil en TinkuBot.* "
        "La información que agregaste nos ayuda a conectarte mejor con clientes "
        "que realmente necesitan tus servicios. Ahora nuestro equipo lo está "
        "revisando y, si hace falta algo más, te escribimos."
    )
