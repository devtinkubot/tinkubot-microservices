"""Vistas interactivas de detalle para el menú de proveedor."""

import os
from typing import Any, Dict, Optional

from infrastructure.database import get_supabase_client
from infrastructure.storage import construir_url_media_publica
from infrastructure.storage.almacenamiento_imagenes import SUPABASE_PROVIDERS_BUCKET
from services import listar_certificados_proveedor
from services.servicios_proveedor.constantes import (
    CERTIFICADOS_MAXIMOS,
    SERVICIOS_MAXIMOS,
)
from templates.interfaz import (
    CERTIFICATE_ADD_ID,
    CERTIFICATE_BACK_ID,
    CERTIFICATE_SELECT_PREFIX,
    DETAIL_ACTION_BACK,
    DETAIL_ACTION_CERTIFICATES_ADD,
    DETAIL_ACTION_CERTIFICATES_DELETE,
    DETAIL_ACTION_CITY_CHANGE,
    DETAIL_ACTION_DNI_BACK_CHANGE,
    DETAIL_ACTION_DNI_FRONT_CHANGE,
    DETAIL_ACTION_NAME_CHANGE,
    DETAIL_ACTION_PHOTO_CHANGE,
    DETAIL_ACTION_SERVICES_ADD,
    DETAIL_ACTION_SERVICES_REMOVE,
    DETAIL_ACTION_SOCIAL_CHANGE,
    payload_detalle_certificado,
    payload_detalle_foto,
    payload_detalle_nombre,
    payload_detalle_red_social,
    payload_detalle_servicios,
    payload_detalle_ubicacion,
    payload_lista_certificados,
    payload_lista_eliminar_servicios,
    payload_submenu_informacion_personal,
    payload_submenu_informacion_profesional,
)
from templates.registro import payload_certificado_opcional, preguntar_nombre
from templates.interfaz import (
    solicitar_dni_frontal_actualizacion,
    solicitar_dni_reverso_actualizacion,
    solicitar_red_social_actualizacion,
)
from templates.registro import solicitar_ciudad_actualizacion
from templates.interfaz import solicitar_dni_actualizacion, solicitar_selfie_actualizacion


PERSONAL_PARENT_STATE = "awaiting_personal_info_action"
PROFESSIONAL_PARENT_STATE = "awaiting_professional_info_action"


def _valor_visible(valor: Any, predeterminado: str = "No registrado") -> str:
    texto = str(valor or "").strip()
    return texto or predeterminado


def _resolver_media_url(url_cruda: Any) -> str:
    url_resuelta = construir_url_media_publica(
        str(url_cruda or "").strip(),
        supabase=get_supabase_client(),
        bucket=SUPABASE_PROVIDERS_BUCKET,
        supabase_base_url=os.getenv("SUPABASE_URL", ""),
    )
    url_resuelta = str(url_resuelta or "").strip()
    if url_resuelta and "://" in url_resuelta and not url_resuelta.endswith("?"):
        return url_resuelta
    return ""


async def render_profile_view(
    *,
    flujo: Dict[str, Any],
    estado: str,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    if estado == "viewing_personal_name":
        return payload_detalle_nombre(_valor_visible(flujo.get("full_name")))

    if estado == "viewing_personal_city":
        return payload_detalle_ubicacion(_valor_visible(flujo.get("city"), "No registrada"))

    if estado == "viewing_personal_photo":
        return payload_detalle_foto(
            titulo="Foto de perfil",
            descripcion="Esta es tu foto de perfil actual.",
            media_url=_resolver_media_url(flujo.get("face_photo_url")),
            change_id=DETAIL_ACTION_PHOTO_CHANGE,
        )

    if estado == "viewing_personal_dni_front":
        return payload_detalle_foto(
            titulo="Cédula frontal",
            descripcion="Esta es la foto frontal de tu cédula.",
            media_url=_resolver_media_url(flujo.get("dni_front_photo_url")),
            change_id=DETAIL_ACTION_DNI_FRONT_CHANGE,
        )

    if estado == "viewing_personal_dni_back":
        return payload_detalle_foto(
            titulo="Cédula reverso",
            descripcion="Esta es la foto reverso de tu cédula.",
            media_url=_resolver_media_url(flujo.get("dni_back_photo_url")),
            change_id=DETAIL_ACTION_DNI_BACK_CHANGE,
        )

    if estado == "viewing_professional_services":
        return payload_detalle_servicios(list(flujo.get("services") or []), SERVICIOS_MAXIMOS)

    if estado == "viewing_professional_social":
        return payload_detalle_red_social(_valor_visible(flujo.get("social_media_url"), "No registrada"))

    if estado == "viewing_professional_certificates":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        return payload_lista_certificados(certificados, max_certificados=CERTIFICADOS_MAXIMOS)

    if estado == "viewing_professional_certificate":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        seleccionado = str(flujo.get("selected_certificate_id") or "").strip()
        certificado = next(
            (item for item in certificados if str(item.get("id") or "").strip() == seleccionado),
            {},
        )
        if not certificado:
            if certificados:
                flujo["state"] = "viewing_professional_certificates"
                return payload_lista_certificados(
                    certificados, max_certificados=CERTIFICADOS_MAXIMOS
                )
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return payload_submenu_informacion_profesional()
        return payload_detalle_certificado(
            certificado=certificado,
            total=len(certificados),
            max_certificados=CERTIFICADOS_MAXIMOS,
        )

    return payload_submenu_informacion_personal()


async def manejar_vista_perfil(
    *,
    flujo: Dict[str, Any],
    estado: str,
    texto_mensaje: str,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    texto = (texto_mensaje or "").strip().lower()

    if estado == "viewing_personal_name":
        if texto == DETAIL_ACTION_NAME_CHANGE:
            flujo["profile_edit_mode"] = "personal_name"
            flujo["profile_return_state"] = "viewing_personal_name"
            flujo["state"] = "awaiting_name"
            return {"success": True, "messages": [{"response": preguntar_nombre()}]}
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_personal()]}

    if estado == "viewing_personal_city":
        if texto == DETAIL_ACTION_CITY_CHANGE:
            flujo["profile_edit_mode"] = "personal_city"
            flujo["profile_return_state"] = "viewing_personal_city"
            flujo["state"] = "awaiting_city"
            return {"success": True, "messages": [solicitar_ciudad_actualizacion()]}
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_personal()]}

    if estado == "viewing_personal_photo":
        if texto == DETAIL_ACTION_PHOTO_CHANGE:
            flujo["profile_return_state"] = "viewing_personal_photo"
            flujo["state"] = "awaiting_face_photo_update"
            return {"success": True, "messages": [{"response": solicitar_selfie_actualizacion()}]}
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_personal()]}

    if estado in {"viewing_personal_dni_front", "viewing_personal_dni_back"}:
        if texto == DETAIL_ACTION_DNI_FRONT_CHANGE:
            flujo["profile_edit_mode"] = "personal_dni_front_update"
            flujo["profile_return_state"] = estado
            flujo["state"] = "awaiting_dni_front_photo_update"
            return {
                "success": True,
                "messages": [{"response": solicitar_dni_frontal_actualizacion()}],
            }
        if texto == DETAIL_ACTION_DNI_BACK_CHANGE:
            flujo["profile_edit_mode"] = "personal_dni_back_update"
            flujo["profile_return_state"] = estado
            flujo["state"] = "awaiting_dni_back_photo_update"
            return {
                "success": True,
                "messages": [{"response": solicitar_dni_reverso_actualizacion()}],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_personal()]}

    if estado == "viewing_professional_services":
        if texto == DETAIL_ACTION_SERVICES_ADD:
            flujo["profile_return_state"] = "viewing_professional_services"
            flujo["state"] = "awaiting_service_add"
            return {"success": True, "response": "Escribe el nuevo servicio que deseas agregar. Si son varios, sepáralos con comas."}
        if texto == DETAIL_ACTION_SERVICES_REMOVE:
            flujo["state"] = "awaiting_service_remove"
            return {
                "success": True,
                "messages": [
                    payload_lista_eliminar_servicios(list(flujo.get("services") or []))
                ],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_profesional()]}

    if estado == "viewing_professional_social":
        if texto == DETAIL_ACTION_SOCIAL_CHANGE:
            flujo["profile_return_state"] = "viewing_professional_social"
            flujo["state"] = "awaiting_social_media_update"
            return {"success": True, "messages": [{"response": solicitar_red_social_actualizacion()}]}
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_profesional()]}

    if estado == "viewing_professional_certificates":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        if not certificados:
            flujo["profile_edit_mode"] = "provider_certificate_add"
            flujo["profile_return_state"] = "viewing_professional_certificate"
            flujo["state"] = "awaiting_certificate"
            flujo.pop("selected_certificate_id", None)
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto == CERTIFICATE_ADD_ID:
            flujo["profile_edit_mode"] = "provider_certificate_add"
            flujo["profile_return_state"] = "viewing_professional_certificate"
            flujo["state"] = "awaiting_certificate"
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto == CERTIFICATE_BACK_ID:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {"success": True, "messages": [payload_submenu_informacion_profesional()]}
        if texto.startswith(CERTIFICATE_SELECT_PREFIX):
            flujo["selected_certificate_id"] = texto.removeprefix(CERTIFICATE_SELECT_PREFIX)
            flujo["state"] = "viewing_professional_certificate"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_certificate",
                        proveedor_id=proveedor_id,
                    )
                ],
            }

    if estado == "viewing_professional_certificate":
        if texto == DETAIL_ACTION_CERTIFICATES_ADD:
            flujo["profile_edit_mode"] = "provider_certificate_replace"
            flujo["profile_return_state"] = "viewing_professional_certificate"
            flujo["state"] = "awaiting_certificate"
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto == DETAIL_ACTION_BACK:
            flujo.pop("selected_certificate_id", None)
            flujo["state"] = "viewing_professional_certificates"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_certificates",
                        proveedor_id=proveedor_id,
                    )
                ],
            }

    return {
        "success": True,
        "messages": [
            await render_profile_view(
                flujo=flujo,
                estado=estado,
                proveedor_id=proveedor_id,
            )
        ],
    }
