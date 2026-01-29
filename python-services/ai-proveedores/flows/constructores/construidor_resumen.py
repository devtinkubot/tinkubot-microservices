"""Constructor de resumen de confirmación."""

from typing import Any, Dict, List


def construir_resumen_confirmacion(flow: Dict[str, Any]) -> str:
    """Construye resumen de confirmación del registro.

    Fase 7: Actualizada para mostrar lista de servicios numerados en lugar de profession.

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

    # Fase 7: Obtener servicios como lista
    servicios: List[str] = flow.get("specialty") or []
    if isinstance(servicios, str):
        # Si por alguna razón viene como string, intentar dividirlo
        servicios = [s.strip() for s in servicios.split(",") if s.strip()]

    city = flow.get("city") or "No especificada"
    name = flow.get("name") or "No especificado"

    # Fase 7: Construir lista de servicios numerados
    if servicios and len(servicios) > 0:
        servicios_text = "\n".join([f"  {i+1}. {srv}" for i, srv in enumerate(servicios)])
    else:
        servicios_text = "  No especificados"

    lines = [
        "-----------------------------",
        "*Por favor confirma tus datos:*",
        "-----------------------------",
        f"- Ciudad: {city}",
        f"- Nombre: {name}",
        # Fase 7: Mostrar lista de servicios numerados
        "- Servicios:",
        servicios_text,
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
