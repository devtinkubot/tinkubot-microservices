"""Mensajes y formateo relacionados con el detalle de proveedores."""

import re
from typing import Any, Dict, List


# ==================== CONSTANTES ====================

instruccion_seleccionar_proveedor = (
    "*Responde con el número del proveedor para ver detalles.*"
)


# ==================== FUNCIONES AUXILIARES ====================

def _negrita(texto: str) -> str:
    texto_limpio = (texto or "").strip()
    if not texto_limpio:
        return ""
    if texto_limpio.startswith("*") and texto_limpio.endswith("*"):
        return texto_limpio
    texto_limpio = texto_limpio.strip("*")
    return f"*{texto_limpio}*"


def _parsear_servicios(valor: Any) -> List[str]:
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    texto = str(valor).strip()
    if not texto:
        return []
    partes = [
        parte.strip() for parte in re.split(r"[;,/|\n]+", texto) if parte.strip()
    ]
    return partes


def _embellecer(texto: Any) -> str:
    if texto is None:
        return ""
    valor = str(texto).strip()
    if not valor:
        return ""
    return valor[0].upper() + valor[1:]


def _formatear_precio(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and valor > 0:
        return f"USD {valor:.2f}".rstrip("0").rstrip(".")
    return str(valor).strip()


def _formatear_linea(etiqueta: str, valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    return f"{etiqueta}: {texto}" if texto else ""


# ==================== FUNCIONES ====================

def bloque_detalle_proveedor(proveedor: Dict[str, Any]) -> str:
    """Ficha detallada del proveedor con submenú numérico."""
    nombre = (
        proveedor.get("name")
        or proveedor.get("provider_name")
        or proveedor.get("full_name")
        or "Proveedor"
    )
    profesion = proveedor.get("profession") or proveedor.get("service_title") or ""
    if not profesion and isinstance(proveedor.get("professions"), list):
        profesion = ", ".join(
            [
                str(item).strip()
                for item in proveedor.get("professions")
                if str(item).strip()
            ]
        )
    profesion = _embellecer(profesion)
    ciudad = _embellecer(proveedor.get("city") or proveedor.get("location_city") or "")
    provincia = _embellecer(proveedor.get("province") or proveedor.get("state") or "")
    precio = _formatear_precio(
        proveedor.get("price_formatted")
        or proveedor.get("price_display")
        or proveedor.get("price")
    )
    experiencia = (
        proveedor.get("experience_years")
        or proveedor.get("experienceYears")
        or proveedor.get("years_of_experience")
    )
    calificacion = proveedor.get("rating")
    url_social = proveedor.get("social_media_url") or proveedor.get("socialMediaUrl")
    tipo_social = proveedor.get("social_media_type") or proveedor.get("socialMediaType")
    servicios = _parsear_servicios(
        proveedor.get("services_list")
        or proveedor.get("servicesList")
        or proveedor.get("services")
        or proveedor.get("servicesRaw")
    )
    servicios = [_embellecer(svc) for svc in servicios if _embellecer(svc)]

    ubicacion = ", ".join([valor for valor in [ciudad, provincia] if valor])
    lineas: List[str] = ["", _negrita(nombre)]
    for entrada in [
        _formatear_linea("Profesión", profesion),
        _formatear_linea("Ubicación", ubicacion),
        _formatear_linea(
            "Experiencia",
            f"{int(experiencia)} año(s)"
            if isinstance(experiencia, (int, float))
            else experiencia,
        ),
    ]:
        if entrada:
            lineas.append(entrada)

    if servicios:
        lineas.append("Servicios:")
        lineas.extend([f"• {svc}" for svc in servicios])

    if precio:
        lineas.append(_formatear_linea("Precio", precio))

    linea_social = _formatear_linea(
        "Redes",
        f"{tipo_social}: {url_social}" if url_social and tipo_social else url_social,
    )
    if linea_social:
        lineas.append(linea_social)

    linea_calificacion = _formatear_linea(
        "Calificación",
        f"{calificacion:.1f}"
        if isinstance(calificacion, (int, float))
        else calificacion,
    )
    if linea_calificacion:
        lineas.append(linea_calificacion)

    lineas.append("")
    return "\n".join(lineas)


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
