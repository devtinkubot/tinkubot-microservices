"""Mensajes relacionados con estados de verificación de proveedores."""

# ==================== FUNCIONES ====================


def mensaje_proveedor_en_revision() -> str:
    """Mensaje cuando el perfil está en revisión."""
    return (
        "**Listo. Estamos revisando tu perfil; si falta algo, te escribimos.**"
    )


def mensaje_proveedor_verificado() -> str:
    """Mensaje cuando el perfil ha sido verificado exitosamente."""
    return (
        "✅ Tu perfil ha sido verificado y autorizado para unirte a la comunidad TinkuBot. "
        "Ya puedes gestionar tu perfil y atender solicitudes de clientes."
    )
