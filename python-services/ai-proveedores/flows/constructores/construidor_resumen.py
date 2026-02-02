"""Constructor de resumen de confirmación."""

from typing import Any, Dict, List


def construir_resumen_confirmacion(flujo: Dict[str, Any]) -> str:
    """Construye resumen de confirmación del registro.

    Fase 7: Actualizada para mostrar lista de servicios numerados en lugar de profession.

    Args:
        flujo: Diccionario con todos los datos del flujo de registro.

    Returns:
        Texto formateado con todos los datos a confirmar.
    """
    correo = flujo.get("email") or "No especificado"
    red_social = flujo.get("social_media_url") or "No especificada"
    tipo_red_social = flujo.get("social_media_type")
    if tipo_red_social and red_social and red_social != "No especificada":
        red_social = f"{red_social} ({tipo_red_social})"

    foto_frente = "Recibida" if flujo.get("dni_front_image") else "Pendiente"
    foto_reverso = "Recibida" if flujo.get("dni_back_image") else "Pendiente"
    selfie = "Recibida" if flujo.get("face_image") else "Pendiente"

    experiencia = flujo.get("experience_years")
    texto_experiencia = (
        f"{experiencia} años"
        if isinstance(experiencia, int) and experiencia > 0
        else "Sin especificar"
    )

    # Fase 7: Obtener servicios como lista
    servicios: List[str] = flujo.get("specialty") or []
    if isinstance(servicios, str):
        # Si por alguna razón viene como string, intentar dividirlo
        servicios = [s.strip() for s in servicios.split(",") if s.strip()]

    ciudad = flujo.get("city") or "No especificada"
    nombre = flujo.get("name") or "No especificado"

    # Fase 7: Construir lista de servicios numerados
    if servicios and len(servicios) > 0:
        texto_servicios = "\n".join(
            [f"  {i+1}. {srv}" for i, srv in enumerate(servicios)]
        )
    else:
        texto_servicios = "  No especificados"

    lineas = [
        "-----------------------------",
        "*Por favor confirma tus datos:*",
        "-----------------------------",
        f"- Ciudad: {ciudad}",
        f"- Nombre: {nombre}",
        # Fase 7: Mostrar lista de servicios numerados
        "- Servicios:",
        texto_servicios,
        f"- Experiencia: {texto_experiencia}",
        f"- Correo: {correo}",
        f"- Red Social: {red_social}",
        f"- Foto Cédula (frente): {foto_frente}",
        f"- Foto Cédula (reverso): {foto_reverso}",
        f"- Selfie: {selfie}",
        "",
        "-----------------------------",
        "1. Confirmar datos",
        "2. Editar información",
        "-----------------------------",
        "*Responde con el numero de tu opcion:*",
    ]
    return "\n".join(lineas)
