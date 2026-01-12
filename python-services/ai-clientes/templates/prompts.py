"""Textos base reutilizables para el servicio de clientes."""

import re
from typing import Any, Dict, List

# Mantener este módulo enfocado en textos y plantillas simples para evitar
# mezclar lógica de flujo con contenido.

mensaje_inicial_solicitud_servicio = "*Cuéntame, ¿qué servicio necesitas hoy?*"
texto_opcion_buscar_otro_servicio = "Buscar otro servicio"
mensaje_confirmando_disponibilidad = (
    "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
)
instruccion_seleccionar_proveedor = (
    "**Responde con el número del proveedor para ver detalles.**"
)

# Consentimiento de protección de datos
mensaje_consentimiento_datos = """¡Hola! Soy TinkuBot, tu asistente virtual para encontrar servicios confiables de forma rápida y segura.

Para poder conectararte con proveedores de servicios, necesito tu consentimiento para compartir tus datos de contacto únicamente con los profesionales seleccionados.

📋 *Información que compartiremos:*
• Tu número de teléfono
• Ciudad donde necesitas el servicio
• Tipo de servicio que solicitas

🔒 *Tus datos están seguros y solo se usan para esta consulta.*

*¿Aceptas compartir tus datos con proveedores?*"""

opciones_consentimiento_textos = ["Acepto", "No acepto"]
opciones_confirmar_nueva_busqueda_textos = [
    f"{texto_opcion_buscar_otro_servicio}",
    "No, por ahora está bien",
]
titulo_confirmacion_repetir_busqueda = "¿Te ayudo con otro servicio?"
pie_instrucciones_respuesta_numerica = "*Responde con el número de tu opción:*"


def _bold(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("**") and stripped.endswith("**"):
        return stripped
    stripped = stripped.strip("*")
    return f"**{stripped}**"


def mensaje_intro_listado_proveedores(city: str) -> str:
    if city:
        return f"**Encontré estas opciones en {city}:**"
    return "**Encontré estas opciones para ti:**"


def bloque_listado_proveedores_compacto(providers: List[Dict[str, Any]]) -> str:
    """Genera listado de proveedores con números (1-5) y solo nombre."""
    lines: List[str] = [""]
    for idx, provider in enumerate(providers[:5], start=1):
        name = (
            provider.get("name")
            or provider.get("provider_name")
            or provider.get("full_name")
            or "Proveedor"
        ).strip()
        lines.append(f"{idx}) {name}")
    lines.append("")
    return "\n".join(lines)


def bloque_detalle_proveedor(provider: Dict[str, Any]) -> str:
    """Ficha detallada del proveedor con submenú numérico."""

    def parse_services(raw: Any) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        text = str(raw).strip()
        if not text:
            return []
        parts = [
            part.strip() for part in re.split(r"[;,/|\n]+", text) if part.strip()
        ]
        return parts

    def prettify(text: Any) -> str:
        if text is None:
            return ""
        val = str(text).strip()
        if not val:
            return ""
        return val[0].upper() + val[1:]

    def format_price(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, (int, float)) and raw > 0:
            return f"USD {raw:.2f}".rstrip("0").rstrip(".")
        return str(raw).strip()

    def format_line(label: str, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return f"{label}: {text}" if text else ""

    name = (
        provider.get("name")
        or provider.get("provider_name")
        or provider.get("full_name")
        or "Proveedor"
    )
    profession = provider.get("profession") or provider.get("service_title") or ""
    if not profession and isinstance(provider.get("professions"), list):
        profession = ", ".join(
            [
                str(item).strip()
                for item in provider.get("professions")
                if str(item).strip()
            ]
        )
    profession = prettify(profession)
    city = prettify(provider.get("city") or provider.get("location_city") or "")
    province = prettify(provider.get("province") or provider.get("state") or "")
    price = format_price(
        provider.get("price_formatted")
        or provider.get("price_display")
        or provider.get("price")
    )
    experience = (
        provider.get("experience_years")
        or provider.get("experienceYears")
        or provider.get("years_of_experience")
    )
    rating = provider.get("rating")
    social_url = provider.get("social_media_url") or provider.get("socialMediaUrl")
    social_type = provider.get("social_media_type") or provider.get("socialMediaType")
    services = parse_services(
        provider.get("services_list")
        or provider.get("servicesList")
        or provider.get("services")
        or provider.get("servicesRaw")
    )
    services = [prettify(svc) for svc in services if prettify(svc)]

    location = ", ".join([val for val in [city, province] if val])
    lines: List[str] = ["", _bold(name)]
    for entry in [
        format_line("Profesión", profession),
        format_line("Ubicación", location),
        format_line(
            "Experiencia",
            f"{int(experience)} año(s)" if isinstance(experience, (int, float)) else experience,
        ),
    ]:
        if entry:
            lines.append(entry)

    if services:
        lines.append("Servicios:")
        lines.extend([f"• {svc}" for svc in services])

    if price:
        lines.append(format_line("Precio", price))

    social_line = format_line(
        "Redes",
        f"{social_type}: {social_url}" if social_url and social_type else social_url,
    )
    if social_line:
        lines.append(social_line)

    rating_line = format_line(
        "Calificación", f"{rating:.1f}" if isinstance(rating, (int, float)) else rating
    )
    if rating_line:
        lines.append(rating_line)

    lines.append("")
    return "\n".join(lines)


def menu_opciones_detalle_proveedor() -> str:
    """Bloque de acciones para detalle de proveedor."""
    return "\n".join(
        [
            pie_instrucciones_respuesta_numerica,
            "",
            "1) Seleccionar a este proveedor",
            "2) Regresar al listado de proveedores",
            "3) Salir",
        ]
    )


def mensaje_listado_sin_resultados(city: str) -> str:
    lines = [
        mensaje_intro_listado_proveedores(city),
        "",
        "    -- No tenemos aún proveedores --",
        "",
    ]
    return "\n".join(lines)


def mensaje_sin_disponibilidad(service: str, city: str) -> str:
    """Mensaje cuando no hay disponibilidad inmediata en proveedores aceptados."""
    svc_txt = (service or "").strip() or "tu solicitud"
    city_txt = (city or "").strip()
    destino = f"**{svc_txt}**" if svc_txt else "este servicio"
    ciudad = f" en **{city_txt}**" if city_txt else ""
    return (
        f"No hay proveedores disponibles ahora mismo para {destino}{ciudad}. "
        "¿Quieres buscar en otra ciudad o intentarlo más tarde?"
    )


def menu_opciones_consentimiento() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Acepto",
            "2) No acepto",
        ]
    )


def mensajes_flujo_consentimiento() -> List[str]:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{mensaje_consentimiento_datos}",
        f"{pie_instrucciones_respuesta_numerica}\n\n{menu_opciones_consentimiento()}",
    ]


def menu_opciones_confirmacion(include_city_option: bool = False) -> str:
    """Menú de confirmación de búsqueda (solo opciones 1/2/3)."""
    lines: List[str] = []
    if include_city_option:
        lines.extend(
            [
                "1) Buscar en otra ciudad",
                f"2) {opciones_confirmar_nueva_busqueda_textos[0]}",
                "3) Salir",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"1) {opciones_confirmar_nueva_busqueda_textos[0]}",
                "2) Salir",
                "",
            ]
        )
    return "\n".join(lines)


# ============================================================================
# MENSAJES DE VALIDACIÓN Y SEGURIDAD
# ============================================================================

mensaje_error_input_sin_sentido = (
    "No entendí tu mensaje. ¿Podrías decirlo de otra forma?\n\n"
    "Por favor, describe el servicio que necesitas (ej: plomero, electricista)."
)

mensaje_advertencia_contenido_ilegal = (
    "⚠️ Tu mensaje contiene contenido que no está permitido en nuestra plataforma.\n\n"
    "Por favor, mantén una comunicación respetuosa y apropiada."
)

mensaje_ban_usuario = (
    "🚫 Tu cuenta ha sido temporalmente suspendida por infringir nuestras normas.\n\n"
    "Podrás volver a intentarlo a partir de las {hora_reinicio}.\n\n"
    "Si crees que esto es un error, por favor contáctanos."
)
