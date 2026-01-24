"""Mensajes relacionados con estados de verificación de proveedores."""

# ==================== FUNCIONES ====================


def provider_under_review_message() -> str:
    """Mensaje cuando el perfil está en revisión."""
    return (
        "**Listo. Estamos revisando tu perfil; si falta algo, te escribimos.**"
    )


def provider_verified_message() -> str:
    """Mensaje cuando el perfil ha sido verificado exitosamente."""
    return (
        "✅ Tu perfil ha sido verificado y autorizado para unirte a la comunidad TinkuBot. "
        "Ya puedes gestionar tu perfil y atender solicitudes de clientes."
    )


def provider_approved_notification(name: str = "") -> str:
    """Mensaje de notificación cuando el proveedor es aprobado.

    Args:
        name: Nombre del proveedor (opcional). Se usan los primeros 2 palabras.
    """
    parts = [part for part in str(name).split() if part] if name else []
    short_name = " ".join(parts[:2])
    saludo = f"Hola {short_name}," if short_name else "Hola,"
    return (
        f"{saludo} ✅ tu perfil está aprobado. Bienvenido/a a TinkuBot; "
        "permanece pendiente de las próximas solicitudes."
    )
