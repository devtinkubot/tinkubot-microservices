"""Mensajes de revisión propios del contexto onboarding."""


def mensaje_proveedor_en_revision(nombre: str) -> str:
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
