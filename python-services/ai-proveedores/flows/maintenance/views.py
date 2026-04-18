"""Vistas interactivas de detalle para el menú de proveedor."""

import os
from typing import Any, Dict, Optional

from infrastructure.database import get_supabase_client
from infrastructure.storage import construir_url_media_publica
from infrastructure.storage.almacenamiento_imagenes import SUPABASE_PROVIDERS_BUCKET
from services import eliminar_servicio_proveedor, listar_certificados_proveedor
from services.maintenance.constantes import (
    CERTIFICADOS_MAXIMOS,
    SERVICIOS_MAXIMOS,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from services.shared.redes_sociales_slots import (
    SOCIAL_NETWORK_FACEBOOK,
    SOCIAL_NETWORK_INSTAGRAM,
    resolver_redes_sociales,
)
from templates.maintenance import (
    preguntar_nuevo_servicio_con_ejemplos_dinamicos,
    solicitar_red_social_actualizacion,
    solicitar_selfie_actualizacion,
)
from templates.maintenance.ciudad import (
    solicitar_ciudad_actualizacion,
)
from templates.maintenance.menus import (
    CERTIFICATE_ADD_ID,
    CERTIFICATE_BACK_ID,
    CERTIFICATE_SELECT_PREFIX,
    CERTIFICATE_SLOT_PREFIX,
    DETAIL_ACTION_BACK,
    DETAIL_ACTION_CERTIFICATES_ADD,
    DETAIL_ACTION_CITY_CHANGE,
    DETAIL_ACTION_EXPERIENCE_CHANGE,
    DETAIL_ACTION_PHOTO_CHANGE,
    DETAIL_ACTION_SERVICE_CHANGE,
    DETAIL_ACTION_SERVICE_DELETE,
    DETAIL_ACTION_SERVICES_ADD,
    DETAIL_ACTION_SERVICES_REMOVE,
    DETAIL_ACTION_SOCIAL_CHANGE,
    SERVICE_BACK_ID,
    SERVICE_SLOT_PREFIX,
    SOCIAL_NETWORK_BACK_ID,
    SOCIAL_NETWORK_FACEBOOK_ID,
    SOCIAL_NETWORK_INSTAGRAM_ID,
    payload_detalle_certificado,
    payload_detalle_experiencia,
    payload_detalle_foto,
    payload_detalle_nombre,
    payload_detalle_red_social_canal,
    payload_detalle_servicio_individual,
    payload_detalle_servicios,
    payload_detalle_ubicacion,
    payload_lista_certificados,
    payload_lista_eliminar_servicios,
    payload_lista_redes_sociales,
    payload_submenu_informacion_personal,
    payload_submenu_informacion_profesional,
)
from templates.maintenance.registration import (
    payload_certificado_opcional,
    preguntar_experiencia_general,
)
from templates.maintenance.views_labels import (
    etiqueta_apellidos_documento,
    etiqueta_cedula_documento,
    etiqueta_nombres_documento,
    titulo_cedula_frontal,
    titulo_cedula_reverso,
    titulo_facebook,
    titulo_foto_perfil,
    titulo_instagram,
    titulo_nombre_actual,
    valor_no_registrada,
    valor_no_registrado,
)
from templates.shared import (
    descripcion_cedula_frontal_actual,
    descripcion_cedula_reverso_actual,
    descripcion_foto_perfil_actual,
    mensaje_datos_registro,
)

PERSONAL_PARENT_STATE = "maintenance_personal_info_action"
PROFESSIONAL_PARENT_STATE = "maintenance_professional_info_action"
PERSONAL_STATES_SOLO_LECTURA = frozenset(
    {
        "viewing_personal_name",
        "viewing_personal_dni_front",
        "viewing_personal_dni_back",
    }
)


def _cantidad_servicios_para_nuevo_ingreso(flujo: Dict[str, Any]) -> int:
    if flujo.get("profile_completion_mode"):
        temporales = list(flujo.get("servicios_temporales") or [])
        if temporales:
            return len(temporales)
    return len(list(flujo.get("services") or []))


def _estado_compatibilidad_mantenimiento(
    estado_mantenimiento: str,
) -> str:
    return estado_mantenimiento


def _valor_visible(valor: Any, predeterminado: Optional[str] = None) -> str:
    texto = str(valor or "").strip()
    return texto or (predeterminado or valor_no_registrado())


def _formatear_datos_identidad(flujo: Dict[str, Any]) -> str:
    nombre_visible = _valor_visible(
        resolver_nombre_visible_proveedor(proveedor=flujo, fallback=""),
        valor_no_registrado(),
    )
    nombres_documento = _valor_visible(
        flujo.get("document_first_names"),
        valor_no_registrado(),
    )
    apellidos_documento = _valor_visible(
        flujo.get("document_last_names"),
        valor_no_registrado(),
    )
    cedula_documento = _valor_visible(
        flujo.get("document_id_number"),
        valor_no_registrado(),
    )

    partes = [f"{titulo_nombre_actual()}\n{nombre_visible}"]
    if nombres_documento or apellidos_documento or cedula_documento:
        partes.append(
            f"{mensaje_datos_registro()}\n"
            f"{etiqueta_nombres_documento()}{nombres_documento}\n"
            f"{etiqueta_apellidos_documento()}{apellidos_documento}\n"
            f"{etiqueta_cedula_documento()}{cedula_documento}"
        )

    return "\n\n".join(partes)


def _resolver_redes_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return resolver_redes_sociales(flujo)


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
        return payload_detalle_nombre(
            _formatear_datos_identidad(flujo),
            permitir_cambio=False,
        )

    if estado == "viewing_personal_city":
        return payload_detalle_ubicacion(
            _valor_visible(flujo.get("city"), valor_no_registrada())
        )

    if estado == "viewing_personal_photo":
        return payload_detalle_foto(
            titulo=titulo_foto_perfil(),
            descripcion=descripcion_foto_perfil_actual(),
            media_url=_resolver_media_url(flujo.get("face_photo_url")),
            change_id=DETAIL_ACTION_PHOTO_CHANGE,
        )

    if estado == "viewing_personal_dni_front":
        return payload_detalle_foto(
            titulo=titulo_cedula_frontal(),
            descripcion=descripcion_cedula_frontal_actual(),
            media_url=_resolver_media_url(flujo.get("dni_front_photo_url")),
        )

    if estado == "viewing_personal_dni_back":
        return payload_detalle_foto(
            titulo=titulo_cedula_reverso(),
            descripcion=descripcion_cedula_reverso_actual(),
            media_url=_resolver_media_url(flujo.get("dni_back_photo_url")),
        )

    if estado == "viewing_professional_services":
        return payload_detalle_servicios(
            list(flujo.get("services") or []), SERVICIOS_MAXIMOS
        )

    if estado == "viewing_professional_service":
        servicios = list(flujo.get("services") or [])
        raw_idx = flujo.get("selected_service_index")
        indice = int(raw_idx) if raw_idx is not None else -1
        if indice < 0 or indice >= SERVICIOS_MAXIMOS:
            flujo.pop("selected_service_index", None)
            flujo["state"] = "viewing_professional_services"
            return payload_detalle_servicios(servicios, SERVICIOS_MAXIMOS)
        if indice >= len(servicios):
            return payload_detalle_servicio_individual(
                indice=indice,
                servicio="",
                registrado=False,
            )
        return payload_detalle_servicio_individual(
            indice=indice,
            servicio=servicios[indice],
        )

    if estado == "viewing_professional_experience":
        return payload_detalle_experiencia(flujo.get("experience_range"))

    if estado == "viewing_professional_social":
        redes = _resolver_redes_desde_flujo(flujo)
        return payload_lista_redes_sociales(
            facebook_username=redes["facebook_username"],
            instagram_username=redes["instagram_username"],
        )

    if estado == "viewing_professional_social_facebook":
        redes = _resolver_redes_desde_flujo(flujo)
        return payload_detalle_red_social_canal(
            titulo=titulo_facebook(),
            username=redes["facebook_username"],
            url=redes["facebook_url"],
        )

    if estado == "viewing_professional_social_instagram":
        redes = _resolver_redes_desde_flujo(flujo)
        return payload_detalle_red_social_canal(
            titulo=titulo_instagram(),
            username=redes["instagram_username"],
            url=redes["instagram_url"],
        )

    if estado == "viewing_professional_certificates":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        return payload_lista_certificados(
            certificados, max_certificados=CERTIFICADOS_MAXIMOS
        )

    if estado == "viewing_professional_certificate":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        seleccionado = str(flujo.get("selected_certificate_id") or "").strip()
        certificado: Dict[str, Any] = next(
            (
                item
                for item in certificados
                if str(item.get("id") or "").strip() == seleccionado
            ),
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
        media_url = _resolver_media_url(certificado.get("file_url"))
        return payload_detalle_certificado(
            certificado=certificado,
            total=len(certificados),
            max_certificados=CERTIFICADOS_MAXIMOS,
            media_url=media_url,
            body=(
                "Certificado seleccionado."
                if media_url
                else "No pudimos cargar el certificado actual."
            ),
        )

    return payload_submenu_informacion_personal()


async def manejar_vista_perfil(  # noqa: C901
    *,
    flujo: Dict[str, Any],
    estado: str,
    texto_mensaje: str,
    selected_option: Optional[str] = None,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    texto = (selected_option or texto_mensaje or "").strip().lower()

    if estado in PERSONAL_STATES_SOLO_LECTURA:
        flujo.pop("profile_edit_mode", None)
        flujo.pop("profile_return_state", None)
        flujo["state"] = PERSONAL_PARENT_STATE
        return {
            "success": True,
            "messages": [payload_submenu_informacion_personal()],
        }

    if estado == "viewing_personal_name":
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_personal()],
            }

    if estado == "viewing_personal_city":
        if texto == DETAIL_ACTION_CITY_CHANGE:
            flujo["profile_edit_mode"] = "personal_city"
            flujo["profile_return_state"] = "viewing_personal_city"
            flujo["state"] = _estado_compatibilidad_mantenimiento("maintenance_city")
            return {"success": True, "messages": [solicitar_ciudad_actualizacion()]}
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_personal()],
            }

    if estado == "viewing_professional_experience":
        if texto == DETAIL_ACTION_EXPERIENCE_CHANGE:
            flujo["profile_edit_mode"] = "experience"
            flujo["profile_return_state"] = "viewing_professional_experience"
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_experience"
            )
            return {
                "success": True,
                "messages": [{"response": preguntar_experiencia_general()}],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }

    if estado == "viewing_personal_photo":
        if texto == DETAIL_ACTION_PHOTO_CHANGE:
            flujo["profile_return_state"] = "viewing_personal_photo"
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_face_photo_update"
            )
            return {
                "success": True,
                "messages": [{"response": solicitar_selfie_actualizacion()}],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PERSONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_personal()],
            }

    if estado == "viewing_professional_services":
        servicios_actuales = list(flujo.get("services") or [])
        if texto.startswith(SERVICE_SLOT_PREFIX):
            indice_texto = texto.removeprefix(SERVICE_SLOT_PREFIX)
            try:
                posicion = int(indice_texto)
            except ValueError:
                posicion = -1
            if 0 <= posicion < len(servicios_actuales):
                flujo["selected_service_index"] = posicion
                flujo["state"] = "viewing_professional_service"
                return {
                    "success": True,
                    "messages": [
                        await render_profile_view(
                            flujo=flujo,
                            estado="viewing_professional_service",
                            proveedor_id=proveedor_id,
                        )
                    ],
                }
            if 0 <= posicion < SERVICIOS_MAXIMOS:
                flujo["selected_service_index"] = posicion
                flujo["state"] = "viewing_professional_service"
                return {
                    "success": True,
                    "messages": [
                        await render_profile_view(
                            flujo=flujo,
                            estado="viewing_professional_service",
                            proveedor_id=proveedor_id,
                        )
                    ],
                }
        if texto == DETAIL_ACTION_SERVICES_ADD:
            cantidad_actual = _cantidad_servicios_para_nuevo_ingreso(flujo)
            flujo["profile_return_state"] = "viewing_professional_services"
            flujo["state"] = "maintenance_service_add"
            respuesta = await preguntar_nuevo_servicio_con_ejemplos_dinamicos(
                indice=cantidad_actual + 1,
                maximo=SERVICIOS_MAXIMOS,
            )
            flujo["service_examples_lookup"] = (
                respuesta.get("service_examples_lookup") or {}
            )
            return {
                "success": True,
                "messages": [
                    {
                        "response": respuesta.get("response") or "",
                        "ui": respuesta["ui"],
                    }
                ],
            }
        if texto == DETAIL_ACTION_SERVICES_REMOVE:
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_service_remove"
            )
            return {
                "success": True,
                "messages": [
                    payload_lista_eliminar_servicios(list(flujo.get("services") or []))
                ],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo.pop("selected_service_index", None)
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }
        if texto in {SERVICE_BACK_ID, "regresar", "volver", "menu", "menú"}:
            flujo.pop("selected_service_index", None)
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }

    if estado == "viewing_professional_service":
        raw_idx = flujo.get("selected_service_index")
        indice = int(raw_idx) if raw_idx is not None else -1
        servicios_actuales = list(flujo.get("services") or [])
        es_slot_vacio = indice >= len(servicios_actuales)
        if indice < 0 or indice >= SERVICIOS_MAXIMOS:
            flujo.pop("selected_service_index", None)
            flujo["state"] = "viewing_professional_services"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_services",
                        proveedor_id=proveedor_id,
                    )
                ],
            }
        if texto == DETAIL_ACTION_SERVICE_CHANGE:
            flujo["profile_edit_mode"] = (
                "provider_service_add" if es_slot_vacio else "provider_service_replace"
            )
            flujo["profile_edit_service_index"] = indice
            flujo["profile_return_state"] = "viewing_professional_service"
            flujo["state"] = "maintenance_service_add"
            respuesta = await preguntar_nuevo_servicio_con_ejemplos_dinamicos(
                indice=indice + 1,
                maximo=SERVICIOS_MAXIMOS,
            )
            flujo["service_examples_lookup"] = (
                respuesta.get("service_examples_lookup") or {}
            )
            return {
                "success": True,
                "messages": [
                    {
                        "response": respuesta.get("response") or "",
                        "ui": respuesta["ui"],
                    }
                ],
            }
        if texto == DETAIL_ACTION_SERVICE_DELETE and not es_slot_vacio:
            servicios_finales = await eliminar_servicio_proveedor(
                str(proveedor_id or ""),
                indice,
            )
            flujo["services"] = servicios_finales
            flujo.pop("selected_service_index", None)
            flujo["state"] = "viewing_professional_services"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_services",
                        proveedor_id=proveedor_id,
                    )
                ],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = "viewing_professional_services"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_services",
                        proveedor_id=proveedor_id,
                    )
                ],
            }

    if estado == "viewing_professional_social":
        redes = _resolver_redes_desde_flujo(flujo)
        if texto == SOCIAL_NETWORK_FACEBOOK_ID:
            if redes["facebook_username"]:
                flujo["state"] = "viewing_professional_social_facebook"
                return {
                    "success": True,
                    "messages": [
                        await render_profile_view(
                            flujo=flujo,
                            estado="viewing_professional_social_facebook",
                            proveedor_id=proveedor_id,
                        )
                    ],
                }
            flujo["profile_return_state"] = "viewing_professional_social"
            flujo["current_social_network"] = SOCIAL_NETWORK_FACEBOOK
            flujo["state"] = "maintenance_social_facebook_username"
            return {
                "success": True,
                "messages": [
                    {
                        "response": solicitar_red_social_actualizacion(
                            titulo_facebook()
                        ),
                    }
                ],
            }
        if texto == SOCIAL_NETWORK_INSTAGRAM_ID:
            if redes["instagram_username"]:
                flujo["state"] = "viewing_professional_social_instagram"
                return {
                    "success": True,
                    "messages": [
                        await render_profile_view(
                            flujo=flujo,
                            estado="viewing_professional_social_instagram",
                            proveedor_id=proveedor_id,
                        )
                    ],
                }
            flujo["profile_return_state"] = "viewing_professional_social"
            flujo["current_social_network"] = SOCIAL_NETWORK_INSTAGRAM
            flujo["state"] = "maintenance_social_instagram_username"
            return {
                "success": True,
                "messages": [
                    {
                        "response": solicitar_red_social_actualizacion(
                            titulo_instagram()
                        ),
                    }
                ],
            }
        if texto == SOCIAL_NETWORK_BACK_ID:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }
        if texto == DETAIL_ACTION_SOCIAL_CHANGE:
            flujo["state"] = "viewing_professional_social"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_social",
                        proveedor_id=proveedor_id,
                    )
                ],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }

    if estado in {
        "viewing_professional_social_facebook",
        "viewing_professional_social_instagram",
    }:
        red_social = (
            SOCIAL_NETWORK_FACEBOOK
            if estado == "viewing_professional_social_facebook"
            else SOCIAL_NETWORK_INSTAGRAM
        )
        if texto == DETAIL_ACTION_SOCIAL_CHANGE:
            flujo["profile_return_state"] = estado
            flujo["current_social_network"] = red_social
            flujo["state"] = (
                "maintenance_social_facebook_username"
                if red_social == SOCIAL_NETWORK_FACEBOOK
                else "maintenance_social_instagram_username"
            )
            return {
                "success": True,
                "messages": [
                    {
                        "response": solicitar_red_social_actualizacion(
                            titulo_facebook()
                            if red_social == SOCIAL_NETWORK_FACEBOOK
                            else titulo_instagram()
                        ),
                    }
                ],
            }
        if texto == DETAIL_ACTION_BACK:
            flujo["state"] = "viewing_professional_social"
            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado="viewing_professional_social",
                        proveedor_id=proveedor_id,
                    )
                ],
            }

    if estado == "viewing_professional_certificates":
        certificados = await listar_certificados_proveedor(str(proveedor_id or ""))
        flujo["active_certificates"] = certificados
        if texto == CERTIFICATE_ADD_ID:
            flujo["profile_edit_mode"] = "provider_certificate_add"
            flujo["profile_return_state"] = "viewing_professional_certificates"
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_certificate"
            )
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto == CERTIFICATE_BACK_ID:
            flujo["state"] = PROFESSIONAL_PARENT_STATE
            return {
                "success": True,
                "messages": [payload_submenu_informacion_profesional()],
            }
        if texto.startswith(CERTIFICATE_SLOT_PREFIX):
            indice_texto = texto.removeprefix(CERTIFICATE_SLOT_PREFIX)
            try:
                posicion = int(indice_texto)
            except ValueError:
                posicion = -1
            if 0 <= posicion < len(certificados):
                flujo["selected_certificate_id"] = str(
                    certificados[posicion].get("id") or ""
                ).strip()
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
            flujo["profile_edit_mode"] = "provider_certificate_add"
            flujo["profile_return_state"] = "viewing_professional_certificates"
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_certificate"
            )
            flujo.pop("selected_certificate_id", None)
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto.startswith(CERTIFICATE_SELECT_PREFIX):
            flujo["selected_certificate_id"] = texto.removeprefix(
                CERTIFICATE_SELECT_PREFIX
            )
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
            flujo["state"] = _estado_compatibilidad_mantenimiento(
                "maintenance_certificate"
            )
            return {"success": True, "messages": [payload_certificado_opcional()]}
        if texto in {DETAIL_ACTION_BACK, CERTIFICATE_BACK_ID}:
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
