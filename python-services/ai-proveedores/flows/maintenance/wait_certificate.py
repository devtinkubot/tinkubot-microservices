"""Manejador del estado awaiting_certificate."""

from typing import Any, Dict

from flows.constructors import construir_payload_menu_principal
from infrastructure.storage.almacenamiento_imagenes import (
    procesar_imagen_base64_con_metadata,
    subir_imagen_proveedor,
)
from infrastructure.storage.utilidades.extractor_imagen_base64 import (
    extraer_primera_imagen_base64,
)
from services import (
    actualizar_certificado_proveedor,
    agregar_certificado_proveedor,
    eliminar_certificado_proveedor,
    listar_certificados_proveedor,
)
from services.maintenance.constantes import (
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
)
from templates.maintenance import payload_confirmacion_resumen
from templates.maintenance.registration import (
    CERTIFICATE_SKIP_ID,
    construir_resumen_confirmacion_perfil_profesional,
)
from templates.shared import (
    mensaje_certificado_actualizado,
    mensaje_certificado_actualizado_exitosamente,
    mensaje_certificado_agregado_exitosamente,
    mensaje_enviar_certificado_o_omitir,
    mensaje_no_pude_guardar_certificado,
    mensaje_no_pude_identificar_certificado_reemplazo,
    mensaje_no_pude_identificar_perfil_certificado,
    mensaje_no_pude_procesar_imagen_certificado,
)


async def manejar_espera_certificado(
    *,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
) -> Dict[str, Any]:
    texto = (
        str(
            carga.get("message")
            or carga.get("content")
            or carga.get("selected_option")
            or ""
        )
        .strip()
        .lower()
    )
    if texto in {"omitir", CERTIFICATE_SKIP_ID, "skip", "no"}:
        if flujo.get("profile_edit_mode") == "provider_certificate_add":
            flujo.pop("profile_edit_mode", None)
            retorno_estado = (
                str(
                    flujo.pop(
                        "profile_return_state", "viewing_professional_certificates"
                    )
                    or ""
                ).strip()
                or "viewing_professional_certificates"
            )
            flujo["state"] = retorno_estado
            from .views import render_profile_view

            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado=retorno_estado,
                        proveedor_id=str(flujo.get("provider_id") or ""),
                    )
                ],
            }
        if flujo.get("profile_edit_mode") == "provider_certificate_replace":
            flujo.pop("profile_edit_mode", None)
            retorno_estado = (
                str(
                    flujo.pop(
                        "profile_return_state", "viewing_professional_certificate"
                    )
                    or ""
                ).strip()
                or "viewing_professional_certificate"
            )
            flujo["state"] = retorno_estado
            from .views import render_profile_view

            return {
                "success": True,
                "messages": [
                    await render_profile_view(
                        flujo=flujo,
                        estado=retorno_estado,
                        proveedor_id=str(flujo.get("provider_id") or ""),
                    )
                ],
            }
        flujo["pending_certificate_file_url"] = None
        flujo["certificate_uploaded"] = False
        if flujo.get("profile_edit_mode") == "certificate":
            flujo.pop("profile_edit_mode", None)
            flujo["state"] = "maintenance_profile_completion_confirmation"
            return {
                "success": True,
                "messages": [
                    payload_confirmacion_resumen(
                        construir_resumen_confirmacion_perfil_profesional(
                            experience_range=flujo.get("experience_range"),
                            facebook_username=flujo.get("facebook_username"),
                            instagram_username=flujo.get("instagram_username"),
                            certificate_uploaded=bool(
                                flujo.get("certificate_uploaded")
                            ),
                            services=list(flujo.get("servicios_temporales") or []),
                        )
                    )
                ],
            }

        servicios_temporales = list(flujo.get("servicios_temporales") or [])
        flujo["state"] = "maintenance_specialty"
        from .specialty import _mensajes_prompt_servicio_compartido

        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=len(servicios_temporales) + 1,
                maximo_visible=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
            ),
        }

    datos_base64 = extraer_primera_imagen_base64(carga)
    if not datos_base64:
        return {
            "success": True,
            "messages": [{"response": mensaje_enviar_certificado_o_omitir()}],
        }

    proveedor_id = str(flujo.get("provider_id") or "").strip()
    if not proveedor_id:
        return {
            "success": True,
            "messages": [
                {"response": mensaje_no_pude_identificar_perfil_certificado()}
            ],
        }

    procesamiento = await procesar_imagen_base64_con_metadata(
        datos_base64, "certificate"
    )
    bytes_imagen = procesamiento.get("bytes")
    if not bytes_imagen:
        return {
            "success": True,
            "messages": [{"response": mensaje_no_pude_procesar_imagen_certificado()}],
        }

    file_url = await subir_imagen_proveedor(
        proveedor_id,
        bytes_imagen,
        "certificate",
        procesamiento.get("extension") or "jpg",
        procesamiento.get("mimetype") or "image/jpeg",
    )
    if not file_url:
        return {
            "success": True,
            "messages": [{"response": mensaje_no_pude_guardar_certificado()}],
        }

    if flujo.get("profile_edit_mode") == "provider_certificate_update":
        certificados_activos = await listar_certificados_proveedor(proveedor_id)
        for certificado in certificados_activos:
            certificate_id = str(certificado.get("id") or "").strip()
            if certificate_id:
                await eliminar_certificado_proveedor(
                    proveedor_id=proveedor_id,
                    certificate_id=certificate_id,
                )
        agregado = await agregar_certificado_proveedor(
            proveedor_id=proveedor_id,
            file_url=file_url,
        )
        flujo["selected_certificate_id"] = str(
            ((agregado.get("certificate") or {}).get("id") or "")
        ).strip()
        flujo["certificate_uploaded"] = True
        flujo["pending_certificate_file_url"] = file_url
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_certificado_actualizado_exitosamente()},
                construir_payload_menu_principal(
                    esta_registrado=True,
                ),
            ],
        }

    if flujo.get("profile_edit_mode") == "provider_certificate_add":
        agregado = await agregar_certificado_proveedor(
            proveedor_id=proveedor_id,
            file_url=file_url,
        )
        flujo["selected_certificate_id"] = str(
            ((agregado.get("certificate") or {}).get("id") or "")
        ).strip()
        flujo["certificate_uploaded"] = True
        flujo["pending_certificate_file_url"] = file_url
        flujo.pop("profile_edit_mode", None)
        retorno_estado = (
            str(
                flujo.pop("profile_return_state", "viewing_professional_certificate")
                or ""
            ).strip()
            or "viewing_professional_certificate"
        )
        flujo["state"] = retorno_estado
        from .views import render_profile_view

        return {
            "success": True,
            "messages": [
                {"response": mensaje_certificado_agregado_exitosamente()},
                await render_profile_view(
                    flujo=flujo,
                    estado=retorno_estado,
                    proveedor_id=proveedor_id,
                ),
            ],
        }

    if flujo.get("profile_edit_mode") == "provider_certificate_replace":
        certificate_id = str(flujo.get("selected_certificate_id") or "").strip()
        if not certificate_id:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_no_pude_identificar_certificado_reemplazo()}
                ],
            }
        await actualizar_certificado_proveedor(
            proveedor_id=proveedor_id,
            certificate_id=certificate_id,
            file_url=file_url,
        )
        flujo["certificate_uploaded"] = True
        flujo["pending_certificate_file_url"] = file_url
        flujo.pop("profile_edit_mode", None)
        retorno_estado = (
            str(
                flujo.pop("profile_return_state", "viewing_professional_certificate")
                or ""
            ).strip()
            or "viewing_professional_certificate"
        )
        flujo["state"] = retorno_estado
        from .views import render_profile_view

        return {
            "success": True,
            "messages": [
                {"response": mensaje_certificado_actualizado()},
                await render_profile_view(
                    flujo=flujo,
                    estado=retorno_estado,
                    proveedor_id=proveedor_id,
                ),
            ],
        }

    flujo["certificate_uploaded"] = True
    flujo["pending_certificate_file_url"] = file_url
    if flujo.get("profile_edit_mode") == "certificate":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "maintenance_profile_completion_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_resumen(
                    construir_resumen_confirmacion_perfil_profesional(
                        experience_range=flujo.get("experience_range"),
                        facebook_username=flujo.get("facebook_username"),
                        instagram_username=flujo.get("instagram_username"),
                        certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                        services=list(flujo.get("servicios_temporales") or []),
                    )
                )
            ],
        }

    flujo["state"] = "maintenance_specialty"
    servicios_temporales = list(flujo.get("servicios_temporales") or [])
    from .specialty import _mensajes_prompt_servicio_compartido

    return {
        "success": True,
        "messages": await _mensajes_prompt_servicio_compartido(
            flujo=flujo,
            indice=len(servicios_temporales) + 1,
            maximo_visible=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
        ),
    }
