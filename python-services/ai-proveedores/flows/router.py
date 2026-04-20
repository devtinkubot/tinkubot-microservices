"""Router de estados para el flujo de proveedores."""

from typing import Any, Dict, Optional

from flows.constructors import (
    construir_payload_menu_principal,
    construir_respuesta_solicitud_consentimiento,
)
from flows.session import reiniciar_flujo
from routes.availability import manejar_estado_disponibilidad
from routes.maintenance import manejar_contexto_mantenimiento
from routes.onboarding import manejar_contexto_onboarding
from routes.review.router import manejar_revision_proveedor
from services import (
    actualizar_perfil_profesional,
    agregar_certificado_proveedor,
    eliminar_registro_proveedor,
)
from services.onboarding.progress import resolver_checkpoint_onboarding_desde_perfil
from services.review.messages import construir_respuesta_revision
from services.review.state import (
    manejar_bloqueo_revision_posterior,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
)
from services.shared import es_comando_reinicio
from services.shared.estados_proveedor import (
    STANDARD_ONBOARDING_STATES,
    es_proveedor_operativo,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from templates.shared import (
    informar_reinicio_con_eliminacion,
    informar_reinicio_conversacion,
)

_ESTADOS_ONBOARDING_OBSOLETOS_POST_APROBACION = STANDARD_ONBOARDING_STATES | {"confirm"}


def _redirigir_proveedor_aprobado_a_menu(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    logger: Any,
    telefono: str,
) -> Optional[Dict[str, Any]]:
    """Desbloquea al proveedor aprobado que quedó stuck en un estado de onboarding.

    Pasa cuando el admin aprueba mid-onboarding: la BD dice operativo pero el
    flujo Redis conserva un checkpoint obsoleto. Sin este bypass el router trata
    los mensajes como respuestas del onboarding residual.
    """
    if not es_proveedor_operativo(perfil_proveedor):
        return None
    estado_actual = str(flujo.get("state") or "").strip()
    if estado_actual not in _ESTADOS_ONBOARDING_OBSOLETOS_POST_APROBACION:
        return None
    logger.info(
        "🧭 router.redirigir_proveedor_aprobado telefono=%s state_obsoleto=%s "
        "→ awaiting_menu_option",
        telefono,
        estado_actual,
    )
    flujo["state"] = "awaiting_menu_option"
    flujo["mode"] = "operativo"
    flujo.pop("selected_service_index", None)
    return {
        "response": {
            "success": True,
            "messages": [
                construir_payload_menu_principal(esta_registrado=True),
            ],
        },
        "new_flow": flujo,
        "persist_flow": True,
    }


async def _manejar_flujo_sin_estado(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    perfil_proveedor: Optional[Dict[str, Any]],
    logger: Any,
) -> Dict[str, Any]:
    """Resuelve el fallback cuando ningún contexto quiso hacerse cargo."""
    (
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    ) = resolver_estado_registro(flujo, perfil_proveedor)
    provider_id = str(flujo.get("provider_id") or "").strip()
    logger.info(
        "🧭 router.estado_resuelto telefono=%s state=%s consent=%s "
        "registrado=%s verificado=%s pendiente=%s provider_id=%s",
        telefono,
        flujo.get("state"),
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
        provider_id or None,
    )

    if esta_registrado and not esta_verificado:
        respuesta_bloqueo = manejar_bloqueo_revision_posterior(
            flujo=flujo,
            perfil_proveedor=perfil_proveedor,
            esta_verificado=esta_verificado,
        )
        if respuesta_bloqueo is not None:
            return {"response": respuesta_bloqueo, "persist_flow": True}
        flujo["state"] = "review_pending_verification"
        return {
            "response": construir_respuesta_revision(
                resolver_nombre_visible_proveedor(proveedor=flujo)
            ),
            "persist_flow": True,
        }

    if esta_registrado:
        if es_proveedor_operativo(perfil_proveedor):
            flujo["state"] = "awaiting_menu_option"
            return {
                "response": {
                    "success": True,
                    "messages": [
                        construir_payload_menu_principal(
                            esta_registrado=True,
                        )
                    ],
                },
                "persist_flow": True,
            }
        flujo["state"] = "awaiting_menu_option"
        flujo["mode"] = "registration"
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_payload_menu_principal(
                        esta_registrado=False,
                    )
                ],
            },
            "new_flow": flujo,
            "persist_flow": True,
        }

    flujo["state"] = "awaiting_menu_option"
    flujo["mode"] = "registration"
    return {
        "response": {
            "success": True,
            "messages": [
                construir_payload_menu_principal(
                    esta_registrado=False,
                )
            ],
        },
        "new_flow": flujo,
        "persist_flow": True,
    }


async def manejar_mensaje(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any = None,
    subir_medios_identidad,
    logger: Any,
) -> Dict[str, Any]:
    """Procesa el mensaje y devuelve respuesta + control de persistencia."""
    texto_normalizado = (texto_mensaje or "").strip().lower()
    logger.info(
        "🧭 router.manejar_mensaje inicio telefono=%s state=%s "
        "has_consent=%s opcion_menu=%s texto='%s'",
        telefono,
        flujo.get("state"),
        flujo.get("has_consent"),
        opcion_menu,
        texto_mensaje,
    )
    if es_comando_reinicio(texto_normalizado):
        resultado_eliminacion = None
        if supabase:
            resultado_eliminacion = await eliminar_registro_proveedor(
                supabase, telefono
            )
        await reiniciar_flujo(telefono)
        flujo.clear()
        flujo.update({"state": None, "mode": "registration"})
        if resultado_eliminacion and resultado_eliminacion.get("success"):
            mensajes = [{"response": informar_reinicio_con_eliminacion()}]
        else:
            mensajes = [{"response": informar_reinicio_conversacion()}]
        return {
            "response": {"success": True, "messages": mensajes},
            "new_flow": None,
            "persist_flow": False,
        }

    flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
    provider_id = str(flujo.get("provider_id") or "").strip()
    logger.info(
        "🧭 router.contexto_entrada telefono=%s provider_id=%s selected_option=%s",
        telefono,
        provider_id or None,
        str(carga.get("selected_option") or "").strip() or None,
    )
    (
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    ) = resolver_estado_registro(flujo, perfil_proveedor)
    flujo["esta_registrado"] = esta_registrado

    respuesta_redireccion = _redirigir_proveedor_aprobado_a_menu(
        flujo=flujo,
        perfil_proveedor=perfil_proveedor,
        logger=logger,
        telefono=telefono,
    )
    if respuesta_redireccion is not None:
        return respuesta_redireccion

    resultado_enrutado = await enrutar_estado(
        estado=flujo.get("state"),
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        telefono=telefono,
        opcion_menu=opcion_menu,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad,
        logger=logger,
    )
    if resultado_enrutado is not None:
        logger.info(
            "🧭 router.enrutado telefono=%s state=%s persist=%s registered=%s "
            "pending=%s",
            telefono,
            flujo.get("state"),
            resultado_enrutado.get("persist_flow", True),
            esta_registrado,
            esta_pendiente_revision,
        )
        return resultado_enrutado

    return await _manejar_flujo_sin_estado(
        flujo=flujo,
        telefono=telefono,
        perfil_proveedor=perfil_proveedor,
        logger=logger,
    )


async def enrutar_estado(  # noqa: C901
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    texto_mensaje: str,
    carga: Dict[str, Any],
    telefono: str,
    opcion_menu: Optional[str],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any = None,
    subir_medios_identidad,
    logger: Any,
) -> Optional[Dict[str, Any]]:
    """Enruta el estado actual y devuelve un resultado de ruta."""
    if estado == "awaiting_menu_option" and not esta_registrado:
        flujo.clear()
        flujo.update(
            {
                "state": "onboarding_consent",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return {
            "response": construir_respuesta_solicitud_consentimiento(),
            "persist_flow": True,
        }

    if (
        estado == "awaiting_menu_option"
        and esta_registrado
        and perfil_proveedor
        and not es_proveedor_operativo(perfil_proveedor)
    ):
        flujo["state"] = (
            resolver_checkpoint_onboarding_desde_perfil(perfil_proveedor)
            or "onboarding_specialty"
        )
        flujo["mode"] = "registration"
        estado = flujo["state"]

    respuesta_onboarding = await manejar_contexto_onboarding(
        estado=estado,
        flujo=flujo,
        telefono=telefono,
        texto_mensaje=texto_mensaje,
        carga=carga,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad,
        opcion_menu=opcion_menu,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        logger=logger,
    )
    if respuesta_onboarding is not None:
        return respuesta_onboarding

    if not estado:
        return None

    respuesta_revision = manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=perfil_proveedor,
        provider_id=flujo.get("provider_id"),
    )
    if respuesta_revision is not None:
        return {"response": respuesta_revision, "persist_flow": True}

    respuesta_disponibilidad = await manejar_estado_disponibilidad(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        esta_registrado=esta_registrado,
    )
    if respuesta_disponibilidad is not None:
        return respuesta_disponibilidad

    respuesta_mantenimiento = await manejar_contexto_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        carga=carga,
        opcion_menu=opcion_menu,
        selected_option=carga.get("selected_option"),
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        subir_medios_identidad=subir_medios_identidad,
        agregar_certificado_proveedor=agregar_certificado_proveedor,
        actualizar_perfil_profesional=actualizar_perfil_profesional,
    )
    if respuesta_mantenimiento is not None:
        return respuesta_mantenimiento

    return None
