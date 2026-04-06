"""Mensajes y formateo relacionados con el detalle de proveedores."""

import re
from typing import Any, Dict, List

from services.proveedores.identidad import resolver_nombre_visible_proveedor

DETALLE_PROVIDER_MENU = "provider_detail_menu"
DETALLE_PROVIDER_PHOTO = "provider_detail_photo"
DETALLE_PROVIDER_SERVICES = "provider_detail_services"
DETALLE_PROVIDER_SOCIAL = "provider_detail_social"
DETALLE_PROVIDER_CERTS = "provider_detail_certs"
DETALLE_PROVIDER_CONTACT = "provider_detail_contact"
DETALLE_PROVIDER_BACK = "provider_detail_back"
DETALLE_PROVIDER_SUBVIEW_BACK = "provider_detail_subview_back"


def _negrita(texto: str) -> str:
    texto_limpio = (texto or "").strip()
    if not texto_limpio:
        return ""
    if texto_limpio.startswith("*") and texto_limpio.endswith("*"):
        return texto_limpio
    texto_limpio = texto_limpio.strip("*")
    return f"*{texto_limpio}*"


def _parsear_lista(valor: Any) -> List[str]:
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    texto = str(valor).strip()
    if not texto:
        return []
    return [parte.strip() for parte in re.split(r"[;,/|\n]+", texto) if parte.strip()]


def _embellecer(texto: Any) -> str:
    if texto is None:
        return ""
    valor = str(texto).strip()
    if not valor:
        return ""
    return valor[0].upper() + valor[1:]


def _nombre_proveedor(proveedor: Dict[str, Any]) -> str:
    return resolver_nombre_visible_proveedor(proveedor, status="approved", corto=True)


def _ubicacion_proveedor(proveedor: Dict[str, Any]) -> str:
    ciudad = _embellecer(proveedor.get("city") or proveedor.get("location_city") or "")
    provincia = _embellecer(proveedor.get("province") or proveedor.get("state") or "")
    return ", ".join([valor for valor in [ciudad, provincia] if valor])


def _experiencia_proveedor(proveedor: Dict[str, Any]) -> str:
    experiencia_rango = proveedor.get("experience_range") or proveedor.get(
        "experienceRange"
    )
    if isinstance(experiencia_rango, str) and experiencia_rango.strip():
        return experiencia_rango.strip()
    experiencia = proveedor.get("years_of_experience")
    if isinstance(experiencia, (int, float)):
        return f"{int(experiencia)} año(s)"
    return str(experiencia).strip() if experiencia is not None else ""


def _calificacion_proveedor(proveedor: Dict[str, Any]) -> str:
    calificacion = proveedor.get("rating")
    if isinstance(calificacion, (int, float)):
        return f"{calificacion:.1f}"
    return str(calificacion).strip() if calificacion is not None else ""


def servicios_proveedor(proveedor: Dict[str, Any]) -> List[str]:
    servicios = _parsear_lista(
        proveedor.get("services_list")
        or proveedor.get("servicesList")
        or proveedor.get("services")
        or proveedor.get("servicesRaw")
    )
    return [_embellecer(svc) for svc in servicios if _embellecer(svc)]


def certificaciones_proveedor(proveedor: Dict[str, Any]) -> List[Dict[str, str]]:
    candidatos = (
        proveedor.get("certifications")
        or proveedor.get("certification_images")
        or proveedor.get("certification_urls")
        or proveedor.get("certificate_images")
        or proveedor.get("certificate_urls")
        or []
    )
    certificaciones: List[Dict[str, str]] = []
    if isinstance(candidatos, list):
        for idx, item in enumerate(candidatos, start=1):
            if isinstance(item, dict):
                url = str(
                    item.get("url")
                    or item.get("image_url")
                    or item.get("media_url")
                    or item.get("photo_url")
                    or item.get("file_url")
                    or ""
                ).strip()
                titulo = str(item.get("title") or item.get("name") or "").strip()
            else:
                url = str(item).strip()
                titulo = ""
            if not url:
                continue
            certificaciones.append(
                {
                    "title": titulo or f"Certificación {idx}",
                    "url": url,
                }
            )
    return certificaciones


def resumen_detalle_proveedor(proveedor: Dict[str, Any]) -> str:
    lineas: List[str] = []
    ubicacion = _ubicacion_proveedor(proveedor)
    experiencia = _experiencia_proveedor(proveedor)
    calificacion = _calificacion_proveedor(proveedor)
    if ubicacion:
        lineas.append(f"*Ubicación:* {ubicacion}")
    if experiencia:
        lineas.append(f"*Experiencia:* {experiencia}")
    if calificacion:
        lineas.append(f"*Calificación:* {calificacion}")
    return "\n".join(lineas) or "Selecciona una opción para ver más información."


def bloque_detalle_proveedor(proveedor: Dict[str, Any]) -> str:
    """Resumen corto para el menú principal de detalle."""
    return resumen_detalle_proveedor(proveedor)


def ui_detalle_proveedor(proveedor: Dict[str, Any]) -> Dict[str, Any]:
    """UI tipo lista para navegar los detalles del experto."""
    opciones: List[Dict[str, Any]] = []
    if str(proveedor.get("face_photo_url") or "").strip():
        opciones.append({"id": DETALLE_PROVIDER_PHOTO, "title": "Foto de perfil"})
    if servicios_proveedor(proveedor):
        opciones.append(
            {"id": DETALLE_PROVIDER_SERVICES, "title": "Servicios que ofrece"}
        )
    if str(proveedor.get("social_media_url") or "").strip():
        opciones.append({"id": DETALLE_PROVIDER_SOCIAL, "title": "Redes sociales"})
    if certificaciones_proveedor(proveedor):
        opciones.append({"id": DETALLE_PROVIDER_CERTS, "title": "Certificaciones"})
    opciones.append({"id": DETALLE_PROVIDER_CONTACT, "title": "Contactar"})
    opciones.append({"id": DETALLE_PROVIDER_BACK, "title": "Regresar"})
    return {
        "type": "list",
        "id": "provider_detail_menu_v1",
        "header_type": "text",
        "header_text": _nombre_proveedor(proveedor),
        "list_button_text": "Ver detalles",
        "list_section_title": "Información del experto",
        "options": opciones,
    }


def ui_subvista_detalle_proveedor(*, foto_url: str = "") -> Dict[str, Any]:
    ui = {
        "type": "buttons",
        "id": "provider_detail_subview_v1",
        "options": [
            {
                "id": DETALLE_PROVIDER_SUBVIEW_BACK,
                "title": "Regresar",
            }
        ],
    }
    foto_url = str(foto_url or "").strip()
    if foto_url:
        ui["header_type"] = "image"
        ui["header_media_url"] = foto_url
    return ui


def mensaje_foto_perfil_proveedor(proveedor: Dict[str, Any]) -> Dict[str, Any]:
    nombre = _nombre_proveedor(proveedor)
    return {
        "response": f"*{nombre}*\nFoto de perfil del experto.",
        "ui": ui_subvista_detalle_proveedor(
            foto_url=str(proveedor.get("face_photo_url") or "").strip()
        ),
    }


def mensaje_servicios_proveedor(proveedor: Dict[str, Any]) -> Dict[str, Any]:
    nombre = _nombre_proveedor(proveedor)
    summaries = proveedor.get("service_summaries") or []
    servicios = [_embellecer(s) for s in summaries if s and str(s).strip()] if summaries else servicios_proveedor(proveedor)
    lineas = [f"*{nombre}*", "", "*Servicios que ofrece:*"]
    lineas.extend([f"• {servicio}" for servicio in servicios])
    return {
        "response": "\n".join(lineas),
        "ui": ui_subvista_detalle_proveedor(),
    }


def mensaje_redes_sociales_proveedor(proveedor: Dict[str, Any]) -> Dict[str, Any]:
    nombre = _nombre_proveedor(proveedor)
    red_social_url = str(proveedor.get("social_media_url") or "").strip()
    red_social_tipo = _embellecer(proveedor.get("social_media_type") or "")
    etiqueta = f"{red_social_tipo}: " if red_social_tipo else ""
    return {
        "response": f"*{nombre}*\n*Redes sociales:*\n{etiqueta}{red_social_url}",
        "ui": ui_subvista_detalle_proveedor(),
    }


def mensaje_certificaciones_proveedor(proveedor: Dict[str, Any]) -> Dict[str, Any]:
    nombre = _nombre_proveedor(proveedor)
    certificaciones = certificaciones_proveedor(proveedor)
    primera = certificaciones[0] if certificaciones else {}
    lineas = [f"*{nombre}*", "*Certificaciones:*"]
    lineas.extend([f"• {item['title']}" for item in certificaciones])
    return {
        "response": "\n".join(lineas),
        "ui": ui_subvista_detalle_proveedor(foto_url=primera.get("url", "")),
    }
