"""Resumen de confirmación del registro del proveedor."""

from typing import Any, Dict

from templates.onboarding.registration.confirmacion import (
    mensaje_resumen_confirmacion_registro,
)
from templates.shared.estados import (
    estado_no_especificada,
    estado_no_especificado,
    estado_pendiente,
    estado_recibida,
)


def construir_resumen_confirmacion_registro(flujo: Dict[str, Any]) -> str:
    """Construye el resumen de datos que el proveedor debe confirmar."""
    foto_frente = (
        estado_recibida() if flujo.get("dni_front_image") else estado_pendiente()
    )
    foto_perfil = estado_recibida() if flujo.get("face_image") else estado_pendiente()

    ciudad = flujo.get("city") or estado_no_especificada()
    nombre = flujo.get("name") or estado_no_especificado()

    lineas = [
        mensaje_resumen_confirmacion_registro(),
        "",
        f"- Ciudad: {ciudad}",
        f"- Nombre: {nombre}",
        f"- Foto Cédula (frente): {foto_frente}",
        f"- Foto de perfil: {foto_perfil}",
    ]
    return "\n".join(lineas)
