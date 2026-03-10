"""Mensajes relacionados con estados de verificación de proveedores."""

# ==================== FUNCIONES ====================


def mensaje_proveedor_en_revision(nombre: str) -> str:
    """Mensaje cuando el perfil está en revisión.

    Args:
        nombre: Nombre del proveedor para personalizar el mensaje.
    """
    nombre_limpio = nombre.strip()
    return (
        f"✅ *{nombre_limpio}*, tu perfil en TinkuBot fue registrado y lo estamos revisando; "
        "si falta algo, te escribimos."
    )


def mensaje_proveedor_verificado() -> str:
    """Mensaje cuando el perfil ha sido verificado exitosamente."""
    return (
        "✅ Tu perfil ha sido verificado y autorizado para unirte a la comunidad TinkuBot. "
        "Ya puedes gestionar tu perfil y atender solicitudes de clientes."
    )


def mensaje_perfil_profesional_en_revision() -> str:
    """Mensaje cuando el perfil profesional ya fue enviado a revisión humana."""
    return (
        "✅ Tu perfil profesional fue enviado a revisión. "
        "Te notificaremos cuando quede aprobado."
    )
