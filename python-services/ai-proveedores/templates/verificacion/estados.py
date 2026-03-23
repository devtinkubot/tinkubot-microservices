"""Mensajes relacionados con estados de verificación de proveedores."""

# ==================== FUNCIONES ====================


def mensaje_proveedor_en_revision(nombre: str) -> str:
    """Mensaje cuando el perfil está en revisión.

    Args:
        nombre: Nombre del proveedor para personalizar el mensaje.
    """
    return (
        "✅ Tu registro fue enviado correctamente y está en revisión. "
        "Si necesitamos algo más, te escribimos."
    )


def mensaje_proveedor_verificado() -> str:
    """Mensaje cuando el perfil ha sido verificado exitosamente."""
    return (
        "✅ Tu perfil profesional fue aprobado. "
        "Ya puedes recibir solicitudes de clientes."
    )


def mensaje_perfil_profesional_en_revision() -> str:
    """Mensaje cuando el perfil profesional ya fue enviado a revisión humana."""
    return (
        "✅ Tu registro fue enviado correctamente y está en revisión. "
        "Si necesitamos algo más, te escribimos."
    )
