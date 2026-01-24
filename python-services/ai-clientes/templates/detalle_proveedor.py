"""Mensajes y formateo relacionados con el detalle de proveedores."""

import re
from typing import Any, Dict, List


# ==================== CONSTANTES ====================

instruccion_seleccionar_proveedor = (
    "**Responde con el número del proveedor para ver detalles.**"
)


# ==================== FUNCIONES AUXILIARES ====================

def _bold(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("**") and stripped.endswith("**"):
        return stripped
    stripped = stripped.strip("*")
    return f"**{stripped}**"


def _parse_services(raw: Any) -> List[str]:
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


def _prettify(text: Any) -> str:
    if text is None:
        return ""
    val = str(text).strip()
    if not val:
        return ""
    return val[0].upper() + val[1:]


def _format_price(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (int, float)) and raw > 0:
        return f"USD {raw:.2f}".rstrip("0").rstrip(".")
    return str(raw).strip()


def _format_line(label: str, value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return f"{label}: {text}" if text else ""


# ==================== FUNCIONES ====================

def bloque_detalle_proveedor(provider: Dict[str, Any]) -> str:
    """Ficha detallada del proveedor con submenú numérico."""
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
    profession = _prettify(profession)
    city = _prettify(provider.get("city") or provider.get("location_city") or "")
    province = _prettify(provider.get("province") or provider.get("state") or "")
    price = _format_price(
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
    services = _parse_services(
        provider.get("services_list")
        or provider.get("servicesList")
        or provider.get("services")
        or provider.get("servicesRaw")
    )
    services = [_prettify(svc) for svc in services if _prettify(svc)]

    location = ", ".join([val for val in [city, province] if val])
    lines: List[str] = ["", _bold(name)]
    for entry in [
        _format_line("Profesión", profession),
        _format_line("Ubicación", location),
        _format_line(
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
        lines.append(_format_line("Precio", price))

    social_line = _format_line(
        "Redes",
        f"{social_type}: {social_url}" if social_url and social_type else social_url,
    )
    if social_line:
        lines.append(social_line)

    rating_line = _format_line(
        "Calificación", f"{rating:.1f}" if isinstance(rating, (int, float)) else rating
    )
    if rating_line:
        lines.append(rating_line)

    lines.append("")
    return "\n".join(lines)


def menu_opciones_detalle_proveedor() -> str:
    """Bloque de acciones para detalle de proveedor."""
    from templates.comunes import pie_instrucciones_respuesta_numerica
    return "\n".join(
        [
            pie_instrucciones_respuesta_numerica,
            "",
            "1) Seleccionar a este proveedor",
            "2) Regresar al listado de proveedores",
            "3) Salir",
        ]
    )
