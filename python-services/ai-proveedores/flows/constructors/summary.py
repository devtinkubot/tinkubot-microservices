"""Constructor de resumen de confirmación."""

from typing import Any, Dict


def construir_resumen_confirmacion(flujo: Dict[str, Any]) -> str:
    """Construye resumen de confirmación del registro.

    Args:
        flujo: Diccionario con todos los datos del flujo de registro.

    Returns:
        Texto formateado con todos los datos a confirmar.
    """
    foto_frente = "Recibida" if flujo.get("dni_front_image") else "Pendiente"
    foto_perfil = "Recibida" if flujo.get("face_image") else "Pendiente"

    ciudad = flujo.get("city") or "No especificada"
    nombre = flujo.get("name") or "No especificado"

    lineas = [
        "✅ *Por favor confirma tus datos:*",
        "",
        f"- Ciudad: {ciudad}",
        f"- Nombre: {nombre}",
        f"- Foto Cédula (frente): {foto_frente}",
        f"- Foto de perfil: {foto_perfil}",
    ]
    return "\n".join(lineas)
