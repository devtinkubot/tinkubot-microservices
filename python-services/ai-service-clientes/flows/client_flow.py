"""Lógica modularizada del flujo conversacional de clientes."""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from templates.prompts import (
    CONSENT_BUTTONS,
    CONSENT_PROMPT,
    provider_no_results_block,
    provider_no_results_prompt,
)


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

        try:
            profession, _ = extract_fn("", cleaned)
        except Exception:
            profession = None

        service_val = profession or text
        flow.update({"service": service_val, "state": "awaiting_city"})
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
        respond_fn: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]],
        search_providers_fn: Callable[[str, str], Awaitable[Dict[str, Any]]],
        send_provider_prompt_fn: Callable[[str], Awaitable[Dict[str, Any]]],
        set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
        save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
        confirm_prompt_messages_fn: Callable[..., list[Dict[str, Any]]],
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
            flow["confirm_include_provider_option"] = False
            await set_flow_fn(flow)
            block = provider_no_results_block(city)
            prompt_text = provider_no_results_prompt()
            await save_bot_message_fn(block)
            confirm_msgs = confirm_prompt_messages_fn(
                confirm_prompt_title_default, include_city_option=True
            )
            for cmsg in confirm_msgs:
                response_text = cmsg.get("response")
                if response_text:
                    await save_bot_message_fn(response_text)
            if prompt_text:
                await save_bot_message_fn(prompt_text)
            messages = [{"response": block}, *confirm_msgs]
            if prompt_text:
                messages.append({"response": prompt_text})
            return {"messages": messages}

        flow["providers"] = providers[:5]
        flow["state"] = "presenting_results"
        flow["confirm_include_city_option"] = False
        flow["confirm_include_provider_option"] = len(flow["providers"]) > 1

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
            names = ", ".join(
                [p.get("name") or "Proveedor" for p in flow["providers"]]
            )
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
        formal_connection_message_fn: Callable[[Dict[str, Any], str, str], str],
        confirm_prompt_messages_fn: Callable[..., list[Dict[str, Any]]],
        schedule_feedback_fn: Optional[
            Callable[[str, Dict[str, Any], str, str], Awaitable[None]]
        ],
        logger: Any,
        confirm_title_default: str,
    ) -> Dict[str, Any]:
        """Procesa el estado `presenting_results`.

        Devuelve el payload con los mensajes a enviar (proveedor asignado + confirmación).
        """

        choice = (selected or text or "").strip()
        choice_lower = choice.lower()
        choice_normalized = choice_lower.strip().strip("*").rstrip(".)")
        if choice_normalized in ("0", "opcion 0", "opción 0") or (
            "cambio" in choice_lower and "ciudad" in choice_lower
        ):
            flow["state"] = "awaiting_city"
            flow["city_confirmed"] = False
            flow.pop("providers", None)
            flow.pop("chosen_provider", None)
            flow.pop("confirm_attempts", None)
            flow.pop("confirm_title", None)
            flow.pop("confirm_include_city_option", None)
            flow.pop("confirm_include_provider_option", None)
            await set_flow_fn(flow)
            message = {
                "response": "Entendido, ¿en qué ciudad lo necesitas ahora?",
            }
            await save_bot_message_fn(message["response"])
            return message

        providers_list = flow.get("providers", [])

        provider = None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(providers_list):
                provider = providers_list[idx - 1]

        if not provider and choice.lower().startswith("conectar con"):
            name = choice.split("con", 1)[-1].strip()
            for item in providers_list:
                ref_name = (item.get("name") or "").lower()
                if name.lower().replace("con ", "").strip() in ref_name:
                    provider = item
                    break

        provider = provider or (providers_list or [None])[0]
        flow["chosen_provider"] = provider
        flow["state"] = "confirm_new_search"
        flow["confirm_attempts"] = 0
        flow["confirm_title"] = confirm_title_default
        flow["confirm_include_city_option"] = False
        flow["confirm_include_provider_option"] = len(providers_list) > 1

        message = formal_connection_message_fn(
            provider or {}, flow.get("service", ""), flow.get("city", "")
        )

        await set_flow_fn(flow)
        await save_bot_message_fn(message)

        confirm_msgs = confirm_prompt_messages_fn(
            flow.get("confirm_title") or confirm_title_default,
            include_city_option=flow.get("confirm_include_city_option", False),
            include_provider_option=flow.get("confirm_include_provider_option", False),
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

        return {"messages": [{"response": message}, *confirm_msgs]}

    @staticmethod
    async def handle_confirm_new_search(
        flow: Dict[str, Any],
        text: Optional[str],
        selected: Optional[str],
        reset_flow_fn: Callable[[], Awaitable[None]],
        respond_fn: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]],
        resend_providers_fn: Callable[[], Awaitable[Dict[str, Any]]],
        send_confirm_prompt_fn: Callable[[Dict[str, Any], str], Awaitable[Dict[str, Any]]],
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

        provider_option_enabled = bool(flow.get("confirm_include_provider_option"))

        if choice in {"0", "opcion 0", "opción 0"} and provider_option_enabled:
            flow["state"] = "presenting_results"
            flow.pop("chosen_provider", None)
            flow["confirm_include_provider_option"] = False
            flow["confirm_include_city_option"] = False
            flow["confirm_attempts"] = 0
            return await resend_providers_fn()

        if (
            choice in {"0", "opcion 0", "opción 0"}
            or ("cambio" in choice and "ciudad" in choice)
        ):
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

        yes_choices = {
            "1",
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
            "opcion 1",
            "opción 1",
            "1)",
        }
        no_choices = {
            "2",
            "no",
            "no, por ahora está bien",
            "no gracias",
            "no, gracias",
            "por ahora no",
            "no deseo",
            "no quiero",
            "opcion 2",
            "opción 2",
            "2)",
        }

        if choice in yes_choices:
            await reset_flow_fn()
            if isinstance(flow, dict):
                flow.pop("confirm_attempts", None)
                flow.pop("confirm_title", None)
                flow.pop("confirm_prompt", None)
                flow.pop("confirm_include_city_option", None)
                flow.pop("confirm_include_provider_option", None)
            return await respond_fn(
                {"state": "awaiting_service"},
                {"response": initial_prompt},
            )

        if choice in no_choices:
            await reset_flow_fn()
            await save_bot_message_fn(farewell_message)
            flow.pop("confirm_include_city_option", None)
            flow.pop("confirm_include_provider_option", None)
            return {"response": farewell_message}

        attempts = int(flow.get("confirm_attempts") or 0) + 1
        flow["confirm_attempts"] = attempts

        if attempts >= max_attempts:
            await reset_flow_fn()
            flow.pop("confirm_include_city_option", None)
            flow.pop("confirm_include_provider_option", None)
            return await respond_fn(
                {"state": "awaiting_service"},
                {"response": initial_prompt},
            )

        return await send_confirm_prompt_fn(
            flow,
            flow.get("confirm_title") or confirm_prompt_title_default,
        )
