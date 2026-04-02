"""Mensajes de revisión propios del contexto maintenance."""


def mensaje_proveedor_en_revision(nombre: str) -> str:
    """Mensaje cuando el perfil queda en revisión dentro de maintenance."""
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
