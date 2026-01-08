"""Lógica modularizada del flujo conversacional de clientes."""

import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Union

from templates.prompts import (
    opciones_consentimiento_textos,
    mensaje_consentimiento_datos,
    mensaje_listado_sin_resultados,
)

# Mensaje de error para input inválido
MENSAJE_ERROR_INPUT_INVALIDO = (
    "❌ *Input no válido*\n\n"
    "Por favor describe el servicio que buscas "
    "(ej: plomero, electricista, manicure, doctor)."
)


def validate_service_input(
    text: str,
    greetings: set[str],
    service_catalog: dict[str, set[str]]
) -> tuple[bool, str, Optional[str]]:
    """
    Valida que el input sea estructurado y significativo.

    Retorna: (is_valid, error_message, extracted_service)

    Casos de rechazo:
    - Vacío o saludo
    - Solo números
    - Letra suelta
    - Demasiado corto

    Casos de aceptación:
    - Servicio reconocido del catálogo
    - >= 2 palabras (pasa a extracción)
    """
    cleaned = (text or "").strip()

    # Caso 1: Vacío o saludo
    if not cleaned or cleaned.lower() in greetings:
        return False, "Por favor describe el servicio.", None

    # Caso 2: Solo números
    if cleaned.isdigit():
        return False, MENSAJE_ERROR_INPUT_INVALIDO, None

    # Caso 3: Letra suelta
    if re.fullmatch(r"[a-zA-Z]", cleaned):
        return False, MENSAJE_ERROR_INPUT_INVALIDO, None

    # Caso 4: Demasiado corto
    words = cleaned.split()
    if len(words) < 2 and len(cleaned) < 4:
        return False, MENSAJE_ERROR_INPUT_INVALIDO, None

    # Caso 5: Es servicio reconocido
    normalized = cleaned.lower()
    for service, synonyms in service_catalog.items():
        if normalized in {s.lower() for s in synonyms}:
            return True, "", service

    # Caso 6: Tiene >= 2 palabras (válido, pasará a extracción)
    if len(words) >= 2:
        return True, "", None

    # Caso 7: Inválido por defecto
    return False, MENSAJE_ERROR_INPUT_INVALIDO, None


async def check_city_and_proceed(
    flow: Dict[str, Any],
    customer_profile: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verifica si el usuario YA tiene ciudad confirmada y procede accordingly.

    Si el usuario YA tiene ciudad confirmada, ir directo a búsqueda.
    Si NO tiene ciudad, pedir ciudad normalmente.

    Retorna: Dict con "response" (mensaje para el usuario)
    """
    if not customer_profile:
        return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    existing_city = customer_profile.get("city")
    city_confirmed_at = customer_profile.get("city_confirmed_at")

    if existing_city and city_confirmed_at:
        # Tiene ciudad confirmada: usarla automáticamente
        flow["city"] = existing_city
        flow["city_confirmed"] = True
        flow["state"] = "searching"
        flow["searching_dispatched"] = True

        return {
            "response": (
                f"Perfecto, buscaré {flow.get('service')} en {existing_city}.\n\n"
                f"⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
            ),
            "ui": {"type": "silent"}
        }

    # No tiene ciudad: pedir normalmente
    return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}


class ClientFlow:
    """Encapsula handlers por estado de la conversación."""

    @staticmethod
    def handle_awaiting_service(
        flow: Dict[str, Any],
        text: Optional[str],
        greetings: set[str],
        initial_prompt: str,
        extract_fn: Callable[[str, str], Tuple[Optional[str], Optional[str]]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Procesa el estado `awaiting_service`.

        Retorna una tupla con el flujo actualizado y el payload de respuesta.
        """

        cleaned = (text or "").strip()
        if not cleaned or cleaned.lower() in greetings:
            return flow, {"response": initial_prompt}

        # Evitar que números u opciones sueltas (ej: "1", "2", "a") se toman como servicio
        # NOTA: Permitimos "4" y "5" porque ahora se usan números 1-5 para proveedores
        if re.fullmatch(r"[6-9]\d*", cleaned) or cleaned.lower() in {
            "a",
            "b",
            "c",
            "d",
            "e",
        }:
            return flow, {
                "response": (
                    "Para continuar necesito el nombre del servicio que buscas "
                    "(ej: plomero, electricista, manicure)."
                )
            }

        try:
            profession, _ = extract_fn("", cleaned)
        except Exception:
            profession = None

        service_val = profession or text
        flow.update(
            {
                "service": service_val,
                "service_full": text or service_val,
                "state": "awaiting_city",
            }
        )
        return flow, {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any],
        text: Optional[str],
        city_prompt: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Procesa el estado `awaiting_city`."""

        if not text:
            return flow, {"response": city_prompt}

        flow.update({"city": text, "state": "searching"})
        return flow, {"response": None}

    @staticmethod
    async def handle_searching(
        flow: Dict[str, Any],
        phone: str,
        respond_fn: Callable[
            [Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]
        ],
        search_providers_fn: Callable[[str, str], Awaitable[Dict[str, Any]]],
        send_provider_prompt_fn: Callable[[str], Awaitable[Dict[str, Any]]],
        set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
        initial_prompt: str,
        confirm_prompt_title_default: str,
        logger: Any,
        supabase_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Procesa el estado `searching` ejecutando la búsqueda de proveedores."""

        service = (flow.get("service") or "").strip()
        city = (flow.get("city") or "").strip()

        logger.info(f"🔍 Ejecutando búsqueda: servicio='{service}', ciudad='{city}'")
        logger.info(f"📋 Flujo previo a búsqueda: {flow}")

        if not service or not city:
            if not service and not city:
                flow["state"] = "awaiting_service"
                return await respond_fn(
                    flow,
                    {"response": f"Volvamos a empezar. {initial_prompt}"},
                )
            if not service:
                flow["state"] = "awaiting_service"
                return await respond_fn(
                    flow,
                    {
                        "response": "Perfecto, ¿qué servicio necesitas?",
                    },
                )
            flow["state"] = "awaiting_city"
            return await respond_fn(
                flow,
                {"response": "¿En qué ciudad necesitas " + service + "?"},
            )

        results = await search_providers_fn(service, city)
        providers = results.get("providers") or []
        if not providers:
            flow["state"] = "confirm_new_search"
            flow["confirm_attempts"] = 0
            flow["confirm_title"] = confirm_prompt_title_default
            flow["confirm_include_city_option"] = True
            flow[""] = False
            await set_flow_fn(flow)
            block = mensaje_listado_sin_resultados(city)
            await save_bot_message_fn(block)
            confirm_msgs = mensajes_confirmacion_busqueda_fn(
                confirm_prompt_title_default, include_city_option=True
            )
            for cmsg in confirm_msgs:
                response_text = cmsg.get("response")
                if response_text:
                    await save_bot_message_fn(response_text)
            messages = [{"response": block}, *confirm_msgs]
            return {"messages": messages}

        flow["providers"] = providers[:5]
        flow["state"] = "presenting_results"
        flow["confirm_include_city_option"] = False
        flow[""] = len(flow["providers"]) > 1
        flow.pop("provider_detail_idx", None)

        if supabase_client:
            try:
                supabase_client.table("service_requests").insert(
                    {
                        "phone": phone,
                        "intent": "service_request",
                        "profession": service,
                        "location_city": city,
                        "requested_at": datetime.utcnow().isoformat(),
                        "resolved_at": datetime.utcnow().isoformat(),
                        "suggested_providers": flow["providers"],
                    }
                ).execute()
            except Exception as exc:  # pragma: no cover - logging auxiliar
                logger.warning(f"No se pudo registrar service_request: {exc}")

        try:
            names = ", ".join([p.get("name") or "Proveedor" for p in flow["providers"]])
            logger.info(
                f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])} names=[{names}]"
            )
        except Exception:  # pragma: no cover - logging auxiliar
            logger.info(
                f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])}"
            )

        return await send_provider_prompt_fn(city)

    @staticmethod
    async def handle_presenting_results(
        flow: Dict[str, Any],
        text: Optional[str],
        selected: Optional[str],
        phone: str,
        set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        formal_connection_message_fn: Callable[
            [Dict[str, Any], str, str], Union[Dict[str, Any], str]
        ],
        mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
        schedule_feedback_fn: Optional[
            Callable[[str, Dict[str, Any], str, str], Awaitable[None]]
        ],
        logger: Any,
        confirm_title_default: str,
        bloque_detalle_proveedor_fn: Callable[[Dict[str, Any]], str],
        provider_detail_options_prompt_fn: Callable[[], str],
        initial_prompt: str,
        farewell_message: str,
    ) -> Dict[str, Any]:
        """Procesa el estado `presenting_results` (listado de proveedores)."""

        choice = (selected or text or "").strip()
        choice_lower = choice.lower()
        choice_normalized = choice_lower.strip().strip("*").rstrip(".)")

        providers_list = flow.get("providers", [])

        # Si por alguna razón no hay proveedores en este estado, reiniciar a pedir servicio
        if not providers_list:
            flow.clear()
            flow["state"] = "awaiting_service"
            return {
                "response": initial_prompt,
            }

        provider = None
        if choice_normalized in ("1", "2", "3", "4", "5"):
            idx = int(choice_normalized) - 1
            if 0 <= idx < len(providers_list):
                provider = providers_list[idx]

        if not provider:
            return {
                "response": "Indica el número (1-5) del proveedor que quieres ver."
            }

        flow["state"] = "viewing_provider_detail"
        flow["provider_detail_idx"] = providers_list.index(provider)
        await set_flow_fn(flow)
        detail_message = bloque_detalle_proveedor_fn(provider)
        options_message = provider_detail_options_prompt_fn()
        await save_bot_message_fn(detail_message)
        await save_bot_message_fn(options_message)
        return {
            "messages": [
                {"response": detail_message},
                {"response": options_message},
            ]
        }

    @staticmethod
    async def handle_viewing_provider_detail(
        flow: Dict[str, Any],
        text: Optional[str],
        selected: Optional[str],
        phone: str,
        set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        formal_connection_message_fn: Callable[
            [Dict[str, Any], str, str], Union[Dict[str, Any], str]
        ],
        mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
        schedule_feedback_fn: Optional[
            Callable[[str, Dict[str, Any], str, str], Awaitable[None]]
        ],
        logger: Any,
        confirm_title_default: str,
        send_provider_prompt_fn: Callable[[], Awaitable[Dict[str, Any]]],
        initial_prompt: str,
        farewell_message: str,
        provider_detail_options_prompt_fn: Callable[[], str],
    ) -> Dict[str, Any]:
        """Procesa el estado `viewing_provider_detail` (submenú de detalle)."""

        choice = (selected or text or "").strip()
        choice_lower = choice.lower()
        choice_normalized = choice_lower.strip().strip("*").rstrip(".)")

        providers_list = flow.get("providers", [])
        idx = flow.get("provider_detail_idx")
        provider = None
        if isinstance(idx, int) and 0 <= idx < len(providers_list):
            provider = providers_list[idx]

        if choice_normalized in ("2", "opcion 2", "opción 2", "regresar", "0"):
            flow["state"] = "presenting_results"
            flow.pop("provider_detail_idx", None)
            await set_flow_fn(flow)
            return await send_provider_prompt_fn()

        if choice_normalized in ("3", "opcion 3", "opción 3"):
            for key in [
                "providers",
                "chosen_provider",
                "confirm_attempts",
                "confirm_title",
                "confirm_include_city_option",
                "",
                "provider_detail_idx",
                "service",
            ]:
                flow.pop(key, None)
            flow["state"] = "awaiting_service"
            await set_flow_fn(flow)
            message = {"response": farewell_message}
            await save_bot_message_fn(message["response"])
            return message

        if choice_normalized in ("1", "opcion 1", "opción 1", "elegir"):
            if not provider:
                return {"response": "No encontré ese proveedor, elige otra opción."}
            return await ClientFlow._connect_and_confirm(
                flow,
                provider,
                providers_list,
                phone,
                set_flow_fn,
                save_bot_message_fn,
                formal_connection_message_fn,
                mensajes_confirmacion_busqueda_fn,
                schedule_feedback_fn,
                logger,
                confirm_title_default,
            )

        if choice:
            return {"response": provider_detail_options_prompt_fn()}

        return {"response": provider_detail_options_prompt_fn()}

    @staticmethod
    async def _connect_and_confirm(
        flow: Dict[str, Any],
        provider: Dict[str, Any],
        providers_list: list[Dict[str, Any]],
        phone: str,
        set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        formal_connection_message_fn: Callable[
            [Dict[str, Any], str, str], Union[Dict[str, Any], str]
        ],
        mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
        schedule_feedback_fn: Optional[
            Callable[[str, Dict[str, Any], str, str], Awaitable[None]]
        ],
        logger: Any,
        confirm_title_default: str,
    ) -> Dict[str, Any]:
        """Conecta con proveedor y muestra confirmación posterior."""

        flow.pop("provider_detail_idx", None)
        flow["chosen_provider"] = provider
        flow["state"] = "confirm_new_search"
        flow["confirm_attempts"] = 0
        flow["confirm_title"] = confirm_title_default
        flow["confirm_include_city_option"] = False

        message = formal_connection_message_fn(
            provider or {}, flow.get("service", ""), flow.get("city", "")
        )
        message_obj = message if isinstance(message, dict) else {"response": message}

        await set_flow_fn(flow)
        await save_bot_message_fn(message_obj.get("response"))

        confirm_msgs = mensajes_confirmacion_busqueda_fn(
            flow.get("confirm_title") or confirm_title_default,
            include_city_option=flow.get("confirm_include_city_option", False),
        )
        for cmsg in confirm_msgs:
            await save_bot_message_fn(cmsg.get("response"))

        if schedule_feedback_fn:
            try:
                await schedule_feedback_fn(
                    phone, provider or {}, flow.get("service", ""), flow.get("city", "")
                )
            except Exception as exc:  # pragma: no cover - logging auxiliar
                logger.warning(f"No se pudo agendar feedback: {exc}")

        return {"messages": [message_obj, *confirm_msgs]}

    @staticmethod
    async def handle_confirm_new_search(
        flow: Dict[str, Any],
        text: Optional[str],
        selected: Optional[str],
        reset_flow_fn: Callable[[], Awaitable[None]],
        respond_fn: Callable[
            [Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]
        ],
        resend_providers_fn: Callable[[], Awaitable[Dict[str, Any]]],
        send_confirm_prompt_fn: Callable[
            [Dict[str, Any], str], Awaitable[Dict[str, Any]]
        ],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        initial_prompt: str,
        farewell_message: str,
        confirm_prompt_title_default: str,
        max_attempts: int,
    ) -> Dict[str, Any]:
        """Procesa el estado `confirm_new_search`."""

        choice_raw = (selected or text or "").strip()
        choice = choice_raw.lower().strip()
        choice = choice.rstrip(".!¡¿)")

        provider_option_enabled = bool(flow.get(""))
        city_option_enabled = bool(flow.get("confirm_include_city_option"))

        if choice in {"0", "opcion 0", "opción 0"} and provider_option_enabled:
            flow["state"] = "presenting_results"
            flow.pop("chosen_provider", None)
            flow[""] = False
            flow["confirm_include_city_option"] = False
            flow["confirm_attempts"] = 0
            return await resend_providers_fn()

        city_choices = {"0", "opcion 0", "opción 0"}
        if city_option_enabled:
            city_choices |= {"1", "opcion 1", "opción 1", "1)"}

        if choice in city_choices or ("cambio" in choice and "ciudad" in choice):
            flow["state"] = "awaiting_city"
            flow["city_confirmed"] = False
            flow.pop("providers", None)
            flow.pop("chosen_provider", None)
            flow.pop("confirm_attempts", None)
            flow.pop("confirm_title", None)
            flow.pop("confirm_prompt", None)
            flow.pop("confirm_include_city_option", None)
            return await respond_fn(
                flow,
                {"response": "Entendido, ¿en qué ciudad lo necesitas ahora?"},
            )

        confirm_title = flow.get("confirm_title")
        if not confirm_title:
            legacy_prompt = flow.get("confirm_prompt")
            if isinstance(legacy_prompt, str) and legacy_prompt.strip():
                confirm_title = legacy_prompt.split("\n", 1)[0].strip()
            else:
                confirm_title = confirm_prompt_title_default
            flow["confirm_title"] = confirm_title
            flow.pop("confirm_prompt", None)

        # Mapear numéricamente según si hay opción de ciudad
        base_yes_words = {
            "sí",
            "si",
            "sí, buscar otro servicio",
            "si, buscar otro servicio",
            "sí por favor",
            "si por favor",
            "sí gracias",
            "si gracias",
            "buscar otro servicio",
            "otro servicio",
            "claro",
        }
        base_no_words = {
            "no",
            "no gracias",
            "no, gracias",
            "por ahora no",
            "no deseo",
            "no quiero",
            "salir",
        }

        if city_option_enabled:
            yes_choices = base_yes_words | {
                "2",
                "opcion 2",
                "opción 2",
                "2)",
            }
            no_choices = base_no_words | {
                "3",
                "opcion 3",
                "opción 3",
                "3)",
            }
        else:
            yes_choices = base_yes_words | {
                "1",
                "opcion 1",
                "opción 1",
                "1)",
            }
            no_choices = base_no_words | {
                "2",
                "opcion 2",
                "opción 2",
                "2)",
            }

        if choice in yes_choices:
            preserved_city = flow.get("city")
            preserved_city_confirmed = flow.get("city_confirmed")
            await reset_flow_fn()
            if isinstance(flow, dict):
                flow.pop("confirm_attempts", None)
                flow.pop("confirm_title", None)
                flow.pop("confirm_prompt", None)
                flow.pop("confirm_include_city_option", None)
                flow.pop("", None)
            new_flow: Dict[str, Any] = {"state": "awaiting_service"}
            if preserved_city:
                new_flow["city"] = preserved_city
                if preserved_city_confirmed is not None:
                    new_flow["city_confirmed"] = preserved_city_confirmed
            return await respond_fn(
                new_flow,
                {"response": initial_prompt},
            )

        if choice in no_choices:
            await reset_flow_fn()
            flow.pop("confirm_include_city_option", None)
            flow.pop("", None)
            return await respond_fn(
                {"state": "ended"},
                {"response": farewell_message},
            )

        attempts = int(flow.get("confirm_attempts") or 0) + 1
        flow["confirm_attempts"] = attempts

        if attempts >= max_attempts:
            await reset_flow_fn()
            flow.pop("confirm_include_city_option", None)
            flow.pop("", None)
            return await respond_fn(
                {"state": "awaiting_service"},
                {"response": initial_prompt},
            )

        return await send_confirm_prompt_fn(
            flow,
            flow.get("confirm_title") or confirm_prompt_title_default,
        )
