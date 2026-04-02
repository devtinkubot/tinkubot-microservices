"""Mensajes relacionados con estados de revisión de proveedores."""


def mensaje_proveedor_en_revision(nombre: str) -> str:
    """Mensaje cuando el perfil está en revisión."""
    nombre_limpio = " ".join(str(nombre or "").split()).strip()
    if nombre_limpio:
        return (
            f"✅ Hola {nombre_limpio}, tu registro fue enviado correctamente y "
            "está en revisión. Si necesitamos algo más, te escribimos."
        )
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
    """Mensaje cuando el perfil profesional quedó pendiente de revisión."""
    return (
        "✅ Tu registro fue enviado correctamente y está en revisión. "
        "Si necesitamos algo más, te escribimos."
    )
