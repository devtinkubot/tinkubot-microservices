"""Constructor de resumen de confirmación."""

from typing import Any, Dict


def construir_resumen_confirmacion(flow: Dict[str, Any]) -> str:
    """Construye resumen de confirmación del registro.

    Args:
        flow: Diccionario con todos los datos del flujo de registro.

    Returns:
        Texto formateado con todos los datos a confirmar.
    """
    email = flow.get("email") or "No especificado"
    social = flow.get("social_media_url") or "No especificada"
    social_type = flow.get("social_media_type")
    if social_type and social and social != "No especificada":
        social = f"{social} ({social_type})"

    front = "Recibida" if flow.get("dni_front_image") else "Pendiente"
    back = "Recibida" if flow.get("dni_back_image") else "Pendiente"
    face = "Recibida" if flow.get("face_image") else "Pendiente"

    experience = flow.get("experience_years")
    experience_text = (
        f"{experience} años"
        if isinstance(experience, int) and experience > 0
        else "Sin especificar"
    )
    specialty = flow.get("specialty") or "No especificada"
    city = flow.get("city") or "No especificada"
    profession = flow.get("profession") or "No especificada"
    name = flow.get("name") or "No especificado"

    lines = [
        "-----------------------------",
        "*Por favor confirma tus datos:*",
        "-----------------------------",
        f"- Ciudad: {city}",
        f"- Nombre: {name}",
        f"- Profesion: {profession}",
        f"- Especialidad: {specialty}",
        f"- Experiencia: {experience_text}",
        f"- Correo: {email}",
        f"- Red Social: {social}",
        f"- Foto Cédula (frente): {front}",
        f"- Foto Cédula (reverso): {back}",
        f"- Selfie: {face}",
        "",
        "-----------------------------",
        "1. Confirmar datos",
        "2. Editar información",
        "-----------------------------",
        "*Responde con el numero de tu opcion:*",
    ]
    return "\n".join(lines)
