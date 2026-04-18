"""Servicio de timeout para clientes."""

from datetime import datetime
from typing import Any, Dict, Optional

from flows.mensajes import solicitar_ciudad
from templates.busqueda.confirmacion import (
    mensajes_confirmacion_busqueda,
    titulo_ayuda_otro_servicio,
    titulo_confirmacion_repetir_busqueda,
)
from templates.mensajes.sesion import informar_timeout_inactividad
from templates.proveedores.listado import (
    limpiar_ventana_listado_proveedores,
    mensaje_timeout_listado_proveedores,
)


class ServicioTimeout:
    @staticmethod
    def _listado_proveedores_expirado(flujo: Dict[str, Any], ahora_utc: datetime) -> bool:
        expires_raw = flujo.get("provider_results_expires_at")
        if not expires_raw:
            return False
        try:
            expires_dt = datetime.fromisoformat(str(expires_raw))
        except Exception:
            return False
        return ahora_utc >= expires_dt

    @staticmethod
    async def _manejar_timeout_listado_proveedores(
        orquestador,
        telefono: str,
        flujo: Dict[str, Any],
    ) -> Dict[str, Any]:
        ciudad = (flujo.get("city") or "").strip()
        limpiar_ventana_listado_proveedores(flujo)
        for clave in (
            "providers",
            "chosen_provider",
            "provider_detail_idx",
            "provider_detail_view",
            "availability_request_id",
            "searching_dispatched",
            "searching_started_at",
            "service",
            "service_full",
            "service_captured_after_consent",
            "confirm_attempts",
            "confirm_title",
            "confirm_include_city_option",
        ):
            flujo.pop(clave, None)
        flujo["state"] = "confirm_new_search"
        flujo["confirm_title"] = mensaje_timeout_listado_proveedores(ciudad)
        flujo["confirm_include_city_option"] = False

        ahora_iso = datetime.utcnow().isoformat()
        flujo["last_seen_at"] = ahora_iso
        flujo["last_seen_at_prev"] = ahora_iso

        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.guardar(telefono, flujo)
        else:
            await orquestador.guardar_flujo(telefono, flujo)

        return {
            "messages": mensajes_confirmacion_busqueda(
                mensaje_timeout_listado_proveedores(ciudad),
                incluir_opcion_ciudad=False,
            )
        }

    @staticmethod
    async def verificar_timeout_inactividad(
        orquestador,
        telefono: str,
        flujo: Dict[str, Any],
        contexto: Dict[str, Any],
        estado_actual: Optional[str],
        ahora_utc: datetime,
        ahora_iso: str,
    ) -> Optional[Dict[str, Any]]:
        ultima_vista_cruda = flujo.get("last_seen_at_prev") or flujo.get("last_seen_at")

        if (
            estado_actual not in {"presenting_results", "viewing_provider_detail"}
            or not flujo.get("provider_results_expires_at")
        ) and ultima_vista_cruda:
            try:
                ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda)
                delta_segundos = (ahora_utc - ultima_vista_dt).total_seconds()
                if delta_segundos > 3600:  # 1 hora
                    orquestador.logger.info(
                        "⏰ Timeout inactividad detectado phone=%s state=%s "
                        "delta=%ss last_seen_ref=%s",  # noqa: E501
                        telefono,
                        flujo.get("state"),
                        round(delta_segundos, 2),
                        ultima_vista_cruda,
                    )
                    ciudad_conocida = (flujo.get("city") or "").strip() or (
                        contexto.get("customer_city") or ""
                    ).strip()
                    estado_actual = flujo.get("state")
                    # Estados exentos de timeout normal (tienen manejo especial)
                    if estado_actual == "confirm_new_search":
                        raise ValueError("skip_timeout_for_confirm_new_search")
                    # Eximir retroalimentación de contratación del timeout de 5 min
                    # Es razonable que el usuario tarde horas en responder
                    if estado_actual == "awaiting_hiring_feedback":
                        raise ValueError("skip_timeout_for_awaiting_hiring_feedback")
                    estados_timeout_busqueda = {
                        "searching",
                        "presenting_results",
                        "viewing_provider_detail",
                        "confirm_service",
                    }
                    if estado_actual in estados_timeout_busqueda:
                        flujo.pop("providers", None)
                        flujo.pop("chosen_provider", None)
                        flujo.pop("provider_detail_idx", None)
                        flujo.pop("availability_request_id", None)
                        flujo.pop("confirm_attempts", None)
                        flujo["state"] = "confirm_new_search"
                        flujo["confirm_title"] = titulo_confirmacion_repetir_busqueda
                        flujo["confirm_include_city_option"] = False
                        flujo["last_seen_at"] = ahora_iso
                        flujo["last_seen_at_prev"] = ahora_iso

                        if orquestador.repositorio_flujo:
                            await orquestador.repositorio_flujo.guardar(telefono, flujo)
                        else:
                            await orquestador.guardar_flujo(telefono, flujo)

                        return {
                            "messages": mensajes_confirmacion_busqueda(
                                titulo_confirmacion_repetir_busqueda,
                                incluir_opcion_ciudad=False,
                            )
                        }
                    # Timeout detectado - reiniciar flujo
                    if orquestador.repositorio_flujo:
                        await orquestador.repositorio_flujo.resetear(telefono)
                    else:
                        await orquestador.resetear_flujo(telefono)

                    flujo.clear()
                    flujo.update(
                        {
                            "last_seen_at": ahora_iso,
                            "last_seen_at_prev": ahora_iso,
                        }
                    )

                    # Determinar mensaje según estado real de consentimiento/ciudad
                    tiene_consent = bool(contexto.get("has_consent", False))

                    if not tiene_consent:
                        flujo["state"] = "awaiting_consent"
                        # Obtener prompt de consentimiento
                        if orquestador.servicio_consentimiento:
                            prompt_consentimiento = await orquestador.servicio_consentimiento.solicitar_consentimiento(  # noqa: E501
                                telefono
                            )
                        else:
                            prompt_consentimiento = (
                                await orquestador.solicitar_consentimiento(telefono)
                            )
                        mensajes_timeout = [{"response": informar_timeout_inactividad()}]
                        mensajes_timeout.extend(
                            prompt_consentimiento.get("messages", [prompt_consentimiento])
                        )
                    elif ciudad_conocida:
                        flujo["state"] = "confirm_new_search"
                        flujo["confirm_title"] = titulo_ayuda_otro_servicio
                        flujo["confirm_include_city_option"] = False
                        flujo["city"] = ciudad_conocida
                        flujo["city_confirmed"] = True
                        mensajes_timeout = mensajes_confirmacion_busqueda(
                            titulo_ayuda_otro_servicio,
                            incluir_opcion_ciudad=False,
                        )
                    else:
                        flujo["state"] = "awaiting_city"
                        flujo["onboarding_intro_sent"] = False
                        mensajes_timeout = [
                            {"response": informar_timeout_inactividad()},
                            solicitar_ciudad(),
                        ]

                    # Guardar flujo reseteado
                    if orquestador.repositorio_flujo:
                        await orquestador.repositorio_flujo.guardar(telefono, flujo)
                    else:
                        await orquestador.guardar_flujo(telefono, flujo)

                    return {"messages": mensajes_timeout}
            except Exception as e:
                errores_skip = [
                    "skip_timeout_for_confirm_new_search",
                    "skip_timeout_for_awaiting_hiring_feedback",
                ]
                if str(e) not in errores_skip:
                    orquestador.logger.warning(
                        "Error verificando timeout phone=%s last_seen_ref=%s error=%s",
                        telefono,
                        ultima_vista_cruda,
                        e,
                    )
                pass

        return None
