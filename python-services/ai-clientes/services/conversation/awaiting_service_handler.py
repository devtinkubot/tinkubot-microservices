"""
Awaiting Service Handler - Handles service type input from users

This handler manages the state where the user is expected to provide
the type of service they need.
"""

import asyncio
import logging
from typing import Any, Dict

from flows.client_flow import ClientFlow
from services.search_service import extract_profession_and_location
from services.validation_service import check_if_banned, validate_content_with_ai
from utils.service_catalog import COMMON_SERVICE_SYNONYMS
from templates.prompts import (
    mensaje_error_input_sin_sentido,
    mensaje_advertencia_contenido_ilegal,
    mensaje_ban_usuario,
)
from utils.services_utils import GREETINGS

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class AwaitingServiceHandler(MessageHandler):
    """
    Handler for the 'awaiting_service' conversation state.

    Validates user input, extracts service type, and checks if city
    is already known to proceed directly to search.
    """

    def __init__(
        self,
        customer_service,
        openai_client,
        openai_semaphore,
        session_manager,
        background_search_service,
        templates: Dict[str, Any],
    ):
        """
        Initialize the awaiting service handler.

        Args:
            customer_service: Service for customer management
            openai_client: OpenAI client for content validation
            openai_semaphore: Semaphore for OpenAI rate limiting
            session_manager: Redis session manager
            background_search_service: Background search service
            templates: Dictionary with templates and constants
        """
        self.customer_service = customer_service
        self.openai_client = openai_client
        self.openai_semaphore = openai_semaphore
        self.session_manager = session_manager
        self.background_search_service = background_search_service
        self.templates = templates

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'awaiting_service'
        """
        return state == "awaiting_service"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the service input from user.

        Args:
            context: Contains flow, phone, text, customer_profile,
                     customer_id, respond, and other data

        Returns:
            Response dictionary with messages or response
        """
        from flows.client_flow import validate_service_input, check_city_and_proceed

        flow = context["flow"]
        text = context.get("text", "")
        phone = context["phone"]
        customer_profile = context.get("customer_profile", {})
        respond = context["respond"]

        # 0. Check if user is banned
        if await check_if_banned(phone):
            return await respond(
                flow, {"response": "🚫 Tu cuenta está temporalmente suspendida."}
            )

        # 1. Basic structured validation
        is_valid, error_msg, extracted_service = validate_service_input(
            text or "", GREETINGS, COMMON_SERVICE_SYNONYMS
        )

        if not is_valid:
            return await respond(flow, {"response": error_msg})

        # 2. AI content validation
        should_proceed, warning_msg, ban_msg = await validate_content_with_ai(
            text or "",
            phone,
            openai_client=self.openai_client,
            openai_semaphore=self.openai_semaphore,
            timeout_seconds=self.templates.get("OPENAI_TIMEOUT_SECONDS", 5),
            mensaje_error_input=mensaje_error_input_sin_sentido,
            mensaje_advertencia=mensaje_advertencia_contenido_ilegal,
            mensaje_ban_template=mensaje_ban_usuario,
        )

        if ban_msg:
            return await respond(flow, {"response": ban_msg})

        if warning_msg:
            return await respond(flow, {"response": warning_msg})

        # 3. Extract service using NLP
        updated_flow, reply = ClientFlow.handle_awaiting_service(
            flow,
            text,
            GREETINGS,
            self.templates["mensaje_inicial_solicitud_servicio"],
            extract_profession_and_location,
        )
        flow = updated_flow

        # 4. Check existing city
        city_response = await check_city_and_proceed(flow, customer_profile)

        # 5. If has city, trigger search
        if flow.get("state") == "searching":
            flow["searching_dispatched"] = True
            await self.session_manager.redis_client.set(
                f"flow:{phone}",
                flow,
                expire=self.templates.get("flow_ttl", 3600)
            )
            if self.background_search_service:
                asyncio.create_task(
                    self.background_search_service.search_and_notify(
                        phone,
                        flow.copy(),
                        lambda p, d: self.session_manager.redis_client.set(
                            f"flow:{p}", d
                        )
                    )
                )
            return {"messages": [{"response": city_response.get("response")}]}

        # 6. If no city, ask normally
        return await respond(flow, city_response)
