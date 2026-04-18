"""Manejadores de estados para gestión unificada de servicios."""

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from contracts.repositorios import IRepositorioServiciosProveedor
from dependencies import deps
from flows.constructors import construir_payload_menu_principal
from infrastructure.openai import TransformadorServicios
from infrastructure.redis import cliente_redis
from services.maintenance.asistente_clarificacion import (
    construir_mensaje_clarificacion_servicio,
)
from services.maintenance.constantes import SERVICIOS_MAXIMOS
from services.shared import (
    RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
    RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from services.shared.validacion_semantica import (
    validar_servicio_semanticamente,
)
from templates.maintenance.mensajes_servicios import (
    error_normalizar_servicio,
    payload_confirmacion_servicios_menu,
    preguntar_nuevo_servicio_con_ejemplos_dinamicos,
)
from templates.maintenance.menus import (
    SERVICE_DELETE_BACK_ID,
    SERVICE_DELETE_PREFIX,
    SERVICE_EXAMPLE_ADMIN_ID,
    SERVICE_EXAMPLE_BACK_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_MECHANICS_ID,
    SERVICE_EXAMPLE_PREFIX,
    payload_detalle_servicio_individual,
    payload_lista_eliminar_servicios,
)
from templates.maintenance.registration import SERVICE_CONFIRM_ID, SERVICE_CORRECT_ID
from templates.maintenance.registration.servicios import (
    SERVICE_ACTION_ADD_ID,
    SERVICE_ACTION_BACK_ID,
    SERVICE_ACTION_DELETE_ID,
    payload_menu_servicios_acciones,
)
from templates.shared import (
    mensaje_indica_servicio_exacto,
    mensaje_no_pude_interpretar_servicio_especifico,
)
from utils import (
    dividir_cadena_servicios,
    limpiar_texto_servicio,
)

_FLUJO_KEY_SERVICIOS_TEMP = "service_add_temporales"
_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE = "service_add_confirmation_nonce"
_REDIS_KEY_SERVICIOS_CONFIRMACION_CONSUMIDA = "service_add_confirmation_consumed:{}:{}"
_TTL_CONFIRMACION_SERVICIO_SEGUNDOS = 1800
_EJEMPLOS_SERVICIO = {
    SERVICE_EXAMPLE_MECHANICS_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_ADMIN_ID,
}
_ESTADOS_RETORNO_VISTA_SERVICIOS = {
    "viewing_professional_service",
    "viewing_professional_services",
}


class ManejadorServicios:
    def __init__(self, repositorio: IRepositorioServiciosProveedor) -> None:
        self.repositorio = repositorio

    @staticmethod
    def _estado_retorno_servicios(flujo: Dict[str, Any]) -> str:
        estado = str(flujo.get("profile_return_state") or "").strip()
        if estado in _ESTADOS_RETORNO_VISTA_SERVICIOS:
            return estado
        modo_edicion = str(flujo.get("profile_edit_mode") or "").strip()
        if modo_edicion in {"provider_service_add", "provider_service_replace"}:
            if (
                flujo.get("selected_service_index") is not None
                or flujo.get("profile_edit_service_index") is not None
            ):
                return "viewing_professional_service"
        return ""

    @staticmethod
    def _indice_retorno_servicio(flujo: Dict[str, Any]) -> Optional[int]:
        for clave in ("profile_edit_service_index", "selected_service_index"):
            try:
                indice = int(flujo.get(clave))
            except (TypeError, ValueError):
                continue
            if indice >= 0:
                return indice
        return None

    async def _construir_vista_retorno_servicios(
        self,
        *,
        flujo: Dict[str, Any],
        estado_retorno: str,
        servicios: List[Any],
        proveedor_id: Optional[str],
    ) -> Dict[str, Any]:
        if estado_retorno == "viewing_professional_service":
            indice = self._indice_retorno_servicio(flujo)
            if indice is None:
                indice = max(len(servicios) - 1, 0)
            if 0 <= indice < len(servicios):
                servicio_visible = _texto_visible_servicio(servicios[indice])
            elif servicios:
                servicio_visible = _texto_visible_servicio(servicios[-1])
            else:
                servicio_visible = _texto_visible_servicio(
                    (flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [""])[0]
                )
            return payload_detalle_servicio_individual(
                indice=max(indice, 0),
                servicio=servicio_visible,
                registrado=bool(servicio_visible),
            )

        from .views import render_profile_view

        return await render_profile_view(
            flujo=flujo,
            estado=estado_retorno,
            proveedor_id=proveedor_id,
        )

    async def _persistir_servicios_agregados(
        self,
        *,
        flujo: Dict[str, Any],
        proveedor_id: str,
        servicios_actuales: List[str],
        nuevos_candidatos: List[str],
        aviso_limite: bool = False,
    ) -> Dict[str, Any]:
        servicios_actualizados = servicios_actuales + nuevos_candidatos
        try:
            servicios_finales = await self.repositorio.actualizar_servicios(
                proveedor_id, servicios_actualizados
            )
        except Exception:
            flujo["state"] = "maintenance_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            return {
                "success": True,
                "messages": [
                    _menu_servicios_desde_flujo(flujo, servicios_actuales),
                ],
            }

        flujo["services"] = servicios_finales
        estado_retorno = self._estado_retorno_servicios(flujo)
        retorno_detalle = bool(estado_retorno)
        flujo["state"] = estado_retorno or "maintenance_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)

        if retorno_detalle:
            vista_actualizada = await self._construir_vista_retorno_servicios(
                flujo=flujo,
                estado_retorno=estado_retorno,
                servicios=nuevos_candidatos,
                proveedor_id=proveedor_id,
            )
        else:
            vista_actualizada = _menu_servicios_desde_flujo(flujo, servicios_finales)

        return {"success": True, "messages": [vista_actualizada]}

    async def manejar_accion_servicios(
        self,
        *,
        flujo: Dict[str, Any],
        texto_mensaje: str,
        opcion_menu: Optional[str],
        selected_option: Optional[str] = None,
    ) -> Dict[str, Any]:
        servicios_actuales = flujo.get("services") or []
        seleccion = (selected_option or "").strip().lower()

        if seleccion == SERVICE_ACTION_ADD_ID:
            if len(servicios_actuales) >= SERVICIOS_MAXIMOS:
                return {
                    "success": True,
                    "messages": [
                        _menu_servicios_desde_flujo(flujo, servicios_actuales),
                    ],
                }
            flujo.pop("profile_return_state", None)
            flujo["state"] = "maintenance_service_add"
            return await _construir_prompt_servicio_con_ejemplos(
                flujo=flujo,
                indice=len(servicios_actuales) + 1,
                maximo=SERVICIOS_MAXIMOS,
            )

        if seleccion == SERVICE_ACTION_DELETE_ID:
            if not servicios_actuales:
                flujo["state"] = "maintenance_service_action"
                return {
                    "success": True,
                    "messages": [
                        _menu_servicios_desde_flujo(flujo, servicios_actuales),
                    ],
                }
            flujo["state"] = "maintenance_service_remove"
            return {
                "success": True,
                "messages": [payload_lista_eliminar_servicios(servicios_actuales)],
            }

        if seleccion == SERVICE_ACTION_BACK_ID:
            flujo["state"] = "awaiting_menu_option"
            return {
                "success": True,
                "messages": [_menu_principal_desde_flujo(flujo)],
            }

        return {
            "success": True,
            "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
        }

    async def manejar_accion_servicios_activos(
        self,
        *,
        flujo: Dict[str, Any],
        texto_mensaje: str,
        opcion_menu: Optional[str],
        selected_option: Optional[str] = None,
    ) -> Dict[str, Any]:
        flujo["state"] = "maintenance_service_action"
        return await self.manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
            selected_option=selected_option,
        )

    async def manejar_agregar_servicios(
        self,
        *,
        flujo: Dict[str, Any],
        proveedor_id: Optional[str],
        texto_mensaje: str,
        selected_option: Optional[str] = None,
        cliente_openai: Optional[Any],
        servicio_embeddings: Optional[Any] = None,
    ) -> Dict[str, Any]:
        texto_ingresado = (texto_mensaje or "").strip().lower()
        opcion_seleccionada = (selected_option or "").strip().lower()

        if _es_regreso_desde_ejemplos(texto_ingresado, selected_option):
            return await _retornar_desde_ejemplos(flujo)

        if _es_ejemplo_servicio_seleccionado(
            texto_ingresado
        ) or _es_ejemplo_servicio_seleccionado(opcion_seleccionada):
            flujo["state"] = "maintenance_service_add"
            return await _construir_prompt_servicio_con_ejemplos(
                flujo=flujo,
                indice=(len(list(flujo.get("services") or [])) + 1),
                maximo=SERVICIOS_MAXIMOS,
            )

        if not proveedor_id:
            flujo["state"] = "awaiting_menu_option"
            return {
                "success": True,
                "messages": [_menu_principal_desde_flujo(flujo)],
            }

        servicios_actuales = list(flujo.get("services") or [])
        reemplazo_activo = flujo.get("profile_edit_mode") == "provider_service_replace"
        indice_reemplazo = _resolver_indice_servicio_reemplazo(flujo)
        servicios_base = servicios_actuales
        if (
            reemplazo_activo
            and indice_reemplazo is not None
            and indice_reemplazo < len(servicios_actuales)
        ):
            servicios_base = [
                servicio
                for idx, servicio in enumerate(servicios_actuales)
                if idx != indice_reemplazo
            ]
        espacio_restante = (
            1 if reemplazo_activo else (SERVICIOS_MAXIMOS - len(servicios_actuales))
        )
        if espacio_restante <= 0:
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        candidatos = dividir_cadena_servicios(texto_mensaje or "")
        if not candidatos:
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        if not cliente_openai:
            flujo["state"] = "maintenance_service_action"
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        resultado_normalizacion = await _normalizar_servicios_ingresados(
            texto_mensaje=texto_mensaje or "",
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
            max_servicios=SERVICIOS_MAXIMOS,
            provider_id=proveedor_id,
        )

        if not resultado_normalizacion.get("ok"):
            if resultado_normalizacion.get("needs_clarification"):
                flujo["state"] = "maintenance_service_add"
            else:
                flujo["state"] = "maintenance_service_action"
            return {
                "success": True,
                "messages": [
                    _menu_servicios_desde_flujo(flujo, servicios_actuales),
                ],
            }
        servicios_transformados = resultado_normalizacion.get("services") or []

        nuevos_sanitizados = _normalizar_lista_resultante(
            servicios_transformados, servicios_base
        )
        if not nuevos_sanitizados:
            flujo["state"] = "maintenance_service_action"
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        nuevos_candidatos = nuevos_sanitizados[:espacio_restante]
        if not nuevos_candidatos:
            flujo["state"] = "maintenance_service_action"
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        flujo[_FLUJO_KEY_SERVICIOS_TEMP] = nuevos_candidatos
        flujo[_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE] = uuid4().hex
        flujo["state"] = "maintenance_service_add_confirmation"
        mensajes = [payload_confirmacion_servicios_menu(nuevos_candidatos)]
        if len(nuevos_candidatos) < len(nuevos_sanitizados):
            mensajes.append(payload_confirmacion_servicios_menu(nuevos_candidatos))
        return {"success": True, "messages": mensajes}

    async def manejar_confirmacion_agregar_servicios(
        self,
        *,
        flujo: Dict[str, Any],
        proveedor_id: Optional[str],
        texto_mensaje: str,
        selected_option: Optional[str] = None,
        cliente_openai: Optional[Any],
        servicio_embeddings: Optional[Any] = None,
    ) -> Dict[str, Any]:
        servicios_actuales = list(flujo.get("services") or [])
        reemplazo_activo = flujo.get("profile_edit_mode") == "provider_service_replace"
        indice_reemplazo = _resolver_indice_servicio_reemplazo(flujo)
        if not proveedor_id:
            flujo["state"] = "awaiting_menu_option"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            return {
                "success": True,
                "messages": [_menu_principal_desde_flujo(flujo)],
            }

        texto_limpio = normalizar_texto_interaccion(texto_mensaje)
        opcion_limpia = (selected_option or "").strip().lower()
        decision_aceptar = normalizar_respuesta_binaria(
            texto_limpio,
            RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS
            | RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
            RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS
            | RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
        )
        aceptar = decision_aceptar is True
        if opcion_limpia in {
            SERVICE_CONFIRM_ID,
            "confirm_accept",
            "accept",
        }:
            aceptar = True
        decision_corregir = normalizar_respuesta_binaria(
            texto_limpio,
            RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS
            | RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
            RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS
            | RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
        )
        corregir = decision_corregir is True
        if opcion_limpia in {
            SERVICE_CORRECT_ID,
            "confirm_reject",
            "reject",
        }:
            corregir = True

        confirmacion_nonce = str(
            flujo.get(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE) or ""
        ).strip()

        if corregir:
            if not await _marcar_confirmacion_servicio_consumida(
                str(proveedor_id), confirmacion_nonce
            ):
                flujo["state"] = "viewing_professional_services"
                from .views import render_profile_view

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
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
            flujo["state"] = "maintenance_service_add"
            return await _construir_prompt_servicio_con_ejemplos(
                flujo=flujo,
                indice=(
                    indice_reemplazo + 1
                    if reemplazo_activo and indice_reemplazo is not None
                    else len(servicios_actuales) + 1
                ),
                maximo=SERVICIOS_MAXIMOS,
            )

        if not aceptar:
            candidatos_pendientes = list(flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [])
            if candidatos_pendientes:
                return {
                    "success": True,
                    "messages": [
                        payload_confirmacion_servicios_menu(candidatos_pendientes)
                    ],
                }
            flujo["state"] = "maintenance_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        nuevos_confirmados = list(flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [])
        if not nuevos_confirmados:
            flujo["state"] = "maintenance_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        espacio_restante = (
            1 if reemplazo_activo else (SERVICIOS_MAXIMOS - len(servicios_actuales))
        )
        if espacio_restante <= 0:
            flujo["state"] = "maintenance_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        nuevos_recortados = nuevos_confirmados[:espacio_restante]
        if not await _marcar_confirmacion_servicio_consumida(
            str(proveedor_id), confirmacion_nonce
        ):
            estado_retorno = self._estado_retorno_servicios(flujo)
            flujo["state"] = estado_retorno or "maintenance_service_action"
            if not estado_retorno:
                return {
                    "success": True,
                    "messages": [
                        _menu_servicios_desde_flujo(flujo, servicios_actuales)
                    ],
                }
            return {
                "success": True,
                "messages": [
                    await self._construir_vista_retorno_servicios(
                        flujo=flujo,
                        estado_retorno=estado_retorno,
                        servicios=nuevos_recortados,
                        proveedor_id=proveedor_id,
                    )
                ],
            }
        try:
            if (
                reemplazo_activo
                and indice_reemplazo is not None
                and 0 <= indice_reemplazo < len(servicios_actuales)
            ):
                servicios_para_actualizar = list(servicios_actuales)
                servicios_para_actualizar[indice_reemplazo] = nuevos_recortados[0]
                servicios_finales = await self.repositorio.actualizar_servicios(
                    proveedor_id, servicios_para_actualizar
                )
            else:
                servicios_finales = await self.repositorio.agregar_servicios(
                    proveedor_id, nuevos_recortados
                )
        except Exception:
            flujo["state"] = "maintenance_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        flujo["services"] = servicios_finales
        estado_retorno = self._estado_retorno_servicios(flujo)
        retorno_detalle = bool(estado_retorno)
        flujo["state"] = estado_retorno or "maintenance_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        flujo.pop(_FLUJO_KEY_SERVICIOS_CONFIRMACION_NONCE, None)
        if reemplazo_activo:
            flujo.pop("profile_edit_mode", None)
            flujo.pop("selected_service_index", None)

        if retorno_detalle:
            vista_actualizada = await self._construir_vista_retorno_servicios(
                flujo=flujo,
                estado_retorno=estado_retorno,
                servicios=nuevos_recortados,
                proveedor_id=proveedor_id,
            )
        else:
            vista_actualizada = _menu_servicios_desde_flujo(flujo, servicios_finales)

        return {"success": True, "messages": [vista_actualizada]}

    async def manejar_eliminar_servicio(
        self,
        *,
        flujo: Dict[str, Any],
        proveedor_id: Optional[str],
        texto_mensaje: str,
        selected_option: Optional[str] = None,
    ) -> Dict[str, Any]:
        servicios_actuales = flujo.get("services") or []
        if not proveedor_id or not servicios_actuales:
            flujo["state"] = "awaiting_menu_option"
            return {
                "success": True,
                "messages": [_menu_principal_desde_flujo(flujo)],
            }

        texto_ingresado = (selected_option or texto_mensaje or "").strip()
        if texto_ingresado == SERVICE_DELETE_BACK_ID:
            flujo["state"] = "viewing_professional_services"
            from .views import render_profile_view

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
        indice_servicio = None
        if texto_ingresado.startswith(SERVICE_DELETE_PREFIX):
            try:
                indice_servicio = int(
                    texto_ingresado.removeprefix(SERVICE_DELETE_PREFIX)
                )
            except ValueError:
                indice_servicio = None
        elif texto_ingresado.isdigit():
            indice_servicio = int(texto_ingresado) - 1
        else:
            try:
                indice_servicio = int(re.findall(r"\d+", texto_ingresado)[0]) - 1
            except Exception:
                indice_servicio = None

        if (
            indice_servicio is None
            or indice_servicio < 0
            or indice_servicio >= len(servicios_actuales)
        ):
            return {
                "success": True,
                "messages": [payload_lista_eliminar_servicios(servicios_actuales)],
            }

        try:
            servicios_finales = await self.repositorio.eliminar_servicio(
                proveedor_id, indice_servicio
            )
        except Exception:
            flujo["state"] = "maintenance_service_action"
            return {
                "success": True,
                "messages": [_menu_servicios_desde_flujo(flujo, servicios_actuales)],
            }

        flujo["services"] = servicios_finales
        flujo["state"] = "viewing_professional_services"
        from .views import render_profile_view

        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_services",
                    proveedor_id=proveedor_id,
                ),
            ],
        }


def _resolver_supabase_runtime() -> Any:
    return deps.supabase


def _menu_principal_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return construir_payload_menu_principal(
        esta_registrado=True,
    )


def _menu_servicios_desde_flujo(
    flujo: Dict[str, Any],
    servicios: Optional[List[str]] = None,
) -> Dict[str, Any]:
    servicios_actuales = (
        servicios if servicios is not None else (flujo.get("services") or [])
    )
    return payload_menu_servicios_acciones(servicios_actuales, SERVICIOS_MAXIMOS)


def _nombre_canonico_servicio(servicio: Any) -> str:
    if isinstance(servicio, dict):
        return str(servicio.get("service_name") or "").strip()
    return str(servicio or "").strip()


def _texto_visible_servicio(servicio: Any) -> str:
    if isinstance(servicio, dict):
        return str(
            servicio.get("service_summary")
            or servicio.get("service_name")
            or servicio.get("raw_service_text")
            or ""
        ).strip()
    return str(servicio or "").strip()


async def _marcar_confirmacion_servicio_consumida(
    proveedor_id: str,
    nonce: str,
) -> bool:
    if not proveedor_id or not nonce:
        return True
    return await cliente_redis.set_if_absent(
        _REDIS_KEY_SERVICIOS_CONFIRMACION_CONSUMIDA.format(proveedor_id, nonce),
        {"processed_at": uuid4().hex},
        expire=_TTL_CONFIRMACION_SERVICIO_SEGUNDOS,
    )


def _es_ejemplo_servicio_seleccionado(texto: str) -> bool:
    texto_limpio = (texto or "").strip().lower()
    return (
        texto_limpio.startswith(SERVICE_EXAMPLE_PREFIX)
        or texto_limpio in _EJEMPLOS_SERVICIO
    )


def _es_regreso_desde_ejemplos(texto: str, selected_option: Optional[str]) -> bool:
    texto_limpio = (texto or "").strip().lower()
    seleccionado = (selected_option or "").strip().lower()
    return (
        texto_limpio == SERVICE_EXAMPLE_BACK_ID
        or seleccionado == SERVICE_EXAMPLE_BACK_ID
        or texto_limpio in {"regresar", "volver", "menu", "menú"}
    )


async def _retornar_desde_ejemplos(flujo: Dict[str, Any]) -> Dict[str, Any]:
    flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
    estado_retorno = ManejadorServicios._estado_retorno_servicios(flujo)
    if estado_retorno:
        flujo["state"] = estado_retorno
        servicios_actuales = list(flujo.get("services") or [])
        indice = ManejadorServicios._indice_retorno_servicio(flujo)
        if indice is None:
            indice = max(len(servicios_actuales) - 1, 0)
        if 0 <= indice < len(servicios_actuales):
            servicio_visible = _texto_visible_servicio(servicios_actuales[indice])
        else:
            servicio_visible = _texto_visible_servicio(
                (flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [""])[0]
            )
        return {
            "success": True,
            "messages": [
                payload_detalle_servicio_individual(
                    indice=max(indice, 0),
                    servicio=servicio_visible,
                    registrado=bool(servicio_visible),
                )
            ],
        }

    flujo.pop("profile_return_state", None)
    flujo["state"] = "maintenance_service_action"
    return {
        "success": True,
        "messages": [_menu_servicios_desde_flujo(flujo)],
    }


async def _construir_prompt_servicio_con_ejemplos(
    *,
    flujo: Dict[str, Any],
    indice: int,
    maximo: int,
) -> Dict[str, Any]:
    respuesta = await preguntar_nuevo_servicio_con_ejemplos_dinamicos(
        indice=indice,
        maximo=maximo,
    )
    flujo["service_examples_lookup"] = respuesta.get("service_examples_lookup") or {}
    return {
        "success": True,
        "messages": [
            {
                "response": respuesta.get("response") or "",
                "ui": respuesta["ui"],
            }
        ],
    }


async def _normalizar_servicios_ingresados(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any],
    max_servicios: int,
    provider_id: Optional[str],
) -> Dict[str, Any]:
    if not cliente_openai:
        return {"ok": False, "response": error_normalizar_servicio()}

    try:
        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            texto_mensaje or "",
            max_servicios=max_servicios,
        )
    except Exception:
        return {"ok": False, "response": error_normalizar_servicio()}

    if not servicios_transformados:
        return {"ok": False, "response": error_normalizar_servicio()}

    servicios_validados: List[Dict[str, Any]] = []
    supabase = _resolver_supabase_runtime()
    for servicio in servicios_transformados:
        validacion = await validar_servicio_semanticamente(
            cliente_openai=cliente_openai,
            supabase=supabase,
            raw_service_text=texto_mensaje or "",
            service_name=str(servicio or "").strip(),
        )
        if not validacion.get("is_valid_service") and validacion.get(
            "needs_clarification"
        ):
            contexto = await construir_mensaje_clarificacion_servicio(
                supabase=supabase,
                servicio_embeddings=servicio_embeddings,
                cliente_openai=cliente_openai,
                raw_service_text=texto_mensaje or "",
                service_name=str(
                    validacion.get("normalized_service") or servicio
                ).strip()
                or str(servicio or "").strip(),
                clarification_question=str(
                    validacion.get("clarification_question")
                    or mensaje_indica_servicio_exacto()
                ),
                service_summary=str(
                    validacion.get("proposed_service_summary")
                    or validacion.get("service_summary")
                    or ""
                ).strip()
                or None,
                domain_code=validacion.get("resolved_domain_code")
                or validacion.get("domain_code"),
                category_name=validacion.get("proposed_category_name")
                or validacion.get("category_name"),
            )
            return {
                "ok": False,
                "needs_clarification": True,
                "response": contexto.get("message")
                or str(
                    validacion.get("clarification_question")
                    or mensaje_indica_servicio_exacto()
                ),
            }
        if not validacion.get("is_valid_service"):
            return {
                "ok": False,
                "response": mensaje_no_pude_interpretar_servicio_especifico(),
            }
        servicio_validado = str(
            validacion.get("normalized_service") or servicio
        ).strip()
        if servicio_validado:
            servicios_validados.append(
                {
                    "raw_service_text": str(texto_mensaje or "").strip()
                    or servicio_validado,
                    "service_name": servicio_validado,
                    "service_summary": (
                        str(
                            validacion.get("proposed_service_summary")
                            or validacion.get("service_summary")
                            or ""
                        ).strip()
                        or servicio_validado
                    ),
                    "domain_code": validacion.get("resolved_domain_code")
                    or validacion.get("domain_code"),
                    "category_name": validacion.get("proposed_category_name")
                    or validacion.get("category_name"),
                    "classification_confidence": (
                        validacion.get("classification_confidence")
                        or validacion.get("confidence")
                        or 0.0
                    ),
                    "requires_review": False,
                    "review_reason": validacion.get("reason"),
                }
            )

    return {"ok": True, "services": servicios_validados}


def _normalizar_lista_resultante(
    base_candidatos: List[Dict[str, Any]],
    servicios_actuales: List[str],
) -> List[Dict[str, Any]]:
    nuevos_sanitizados: List[Dict[str, Any]] = []
    claves_actuales = {
        limpiar_texto_servicio(servicio)
        for servicio in servicios_actuales
        if limpiar_texto_servicio(servicio)
    }
    claves_nuevas = set()
    for candidato in base_candidatos:
        service_name = " ".join(_nombre_canonico_servicio(candidato).split())
        service_summary = " ".join(_texto_visible_servicio(candidato).split())
        clave = limpiar_texto_servicio(service_name)
        if not service_name or not clave:
            continue
        if clave in claves_actuales or clave in claves_nuevas:
            continue
        claves_nuevas.add(clave)
        nuevos_sanitizados.append(
            {
                **candidato,
                "service_name": service_name,
                "service_summary": service_summary or service_name,
                "raw_service_text": str(
                    candidato.get("raw_service_text") or service_name
                ).strip()
                or service_name,
            }
        )
    return nuevos_sanitizados


def _resolver_indice_servicio_reemplazo(flujo: Dict[str, Any]) -> Optional[int]:
    try:
        indice = int(flujo.get("selected_service_index"))
    except (TypeError, ValueError):
        return None
    if indice < 0:
        return None
    return indice
