"""Manejador del estado awaiting_certificate."""

from typing import Any, Dict

from infrastructure.storage.almacenamiento_imagenes import (
    procesar_imagen_base64_con_metadata,
    subir_imagen_proveedor,
)
from infrastructure.storage.utilidades.extractor_imagen_base64 import (
    extraer_primera_imagen_base64,
)
from flows.constructores import construir_payload_menu_principal
from services import (
    agregar_certificado_proveedor,
    eliminar_certificado_proveedor,
    listar_certificados_proveedor,
)
from services.servicios_proveedor.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
)
from templates.registro import (
    CERTIFICATE_SKIP_ID,
    construir_resumen_confirmacion_perfil_profesional,
    payload_confirmacion_resumen,
    preguntar_siguiente_servicio_registro,
)


async def manejar_espera_certificado(
    *,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
) -> Dict[str, Any]:
    texto = str(
        carga.get("message") or carga.get("content") or carga.get("selected_option") or ""
    ).strip().lower()
    if texto in {"omitir", CERTIFICATE_SKIP_ID, "skip", "no"}:
        flujo["pending_certificate_file_url"] = None
        flujo["certificate_uploaded"] = False
        if flujo.get("profile_edit_mode") == "certificate":
            flujo.pop("profile_edit_mode", None)
            flujo["state"] = "awaiting_profile_completion_confirmation"
            return {
                "success": True,
                "messages": [
                    payload_confirmacion_resumen(
                        construir_resumen_confirmacion_perfil_profesional(
                            experience_years=flujo.get("experience_years"),
                            social_media_url=flujo.get("social_media_url"),
                            certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                            services=list(flujo.get("servicios_temporales") or []),
                        )
                    )
                ],
            }

        servicios_temporales = list(flujo.get("servicios_temporales") or [])
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios_temporales) + 1,
                        SERVICIOS_MAXIMOS,
                        SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                    )
                }
            ],
        }

    datos_base64 = extraer_primera_imagen_base64(carga)
    if not datos_base64:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Envíame el certificado como imagen o toca *Omitir* para continuar."
                    )
                }
            ],
        }

    proveedor_id = str(flujo.get("provider_id") or "").strip()
    if not proveedor_id:
        return {
            "success": True,
            "messages": [
                {
                    "response": "No pude identificar tu perfil para guardar el certificado. Intenta de nuevo."
                }
            ],
        }

    procesamiento = await procesar_imagen_base64_con_metadata(
        datos_base64, "certificate"
    )
    bytes_imagen = procesamiento.get("bytes")
    if not bytes_imagen:
        return {
            "success": True,
            "messages": [
                {
                    "response": "No pude procesar esa imagen. Envíala de nuevo o toca *Omitir*."
                }
            ],
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
            "messages": [
                {
                    "response": "No pude guardar ese certificado en este momento. Intenta nuevamente o toca *Omitir*."
                }
            ],
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
        await agregar_certificado_proveedor(
            proveedor_id=proveedor_id,
            file_url=file_url,
        )
        flujo["certificate_uploaded"] = True
        flujo["pending_certificate_file_url"] = file_url
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": "✅ Tu certificado activo fue actualizado correctamente."},
                construir_payload_menu_principal(
                    esta_registrado=True,
                    menu_limitado=bool(flujo.get("menu_limitado")),
                    approved_basic=bool(flujo.get("approved_basic")),
                ),
            ],
        }

    flujo["certificate_uploaded"] = True
    flujo["pending_certificate_file_url"] = file_url
    if flujo.get("profile_edit_mode") == "certificate":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_profile_completion_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_resumen(
                    construir_resumen_confirmacion_perfil_profesional(
                        experience_years=flujo.get("experience_years"),
                        social_media_url=flujo.get("social_media_url"),
                        certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                        services=list(flujo.get("servicios_temporales") or []),
                    )
                )
            ],
        }

    flujo["state"] = "awaiting_specialty"
    servicios_temporales = list(flujo.get("servicios_temporales") or [])
    return {
        "success": True,
        "messages": [
            {
                "response": preguntar_siguiente_servicio_registro(
                    len(servicios_temporales) + 1,
                    SERVICIOS_MAXIMOS,
                    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                )
            },
        ],
    }
