"""
Message Processor Service - Servicio de procesamiento de mensajes vía API REST.

Este módulo contiene la lógica de procesamiento de mensajes de clientes
usando OpenAI con contexto de sesión, extracción de entidades y búsqueda de proveedores.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from models.schemas import MessageProcessingResponse

logger = logging.getLogger(__name__)


class MessageProcessorService:
    """
    Servicio para procesamiento de mensajes vía API REST.
    Maneja extracción de entidades con OpenAI y construcción de respuestas.
    """

    def __init__(
        self,
        openai_client,
        extract_profession_and_location,
        intelligent_search_providers_remote,
        search_providers,
        session_manager,
        supabase,
    ):
        """
        Inicializar el servicio de procesamiento de mensajes.

        Args:
            openai_client: Cliente de OpenAI (AsyncOpenAI)
            extract_profession_and_location: Función para extraer profesión y ubicación
            intelligent_search_providers_remote: Función para búsqueda inteligente
            search_providers: Función para búsqueda simple
            session_manager: SessionManager para manejo de sesiones
            supabase: Cliente de Supabase para persistencia
        """
        self.openai_client = openai_client
        self.extract_profession_and_location = extract_profession_and_location
        self.intelligent_search_providers_remote = intelligent_search_providers_remote
        self.search_providers = search_providers
        self.session_manager = session_manager
        self.supabase = supabase

    async def process_message(
        self, request, phone, normalize_profession_for_search, _normalize_token
    ) -> MessageProcessingResponse:
        """
        Procesa mensaje de cliente usando OpenAI con contexto de sesión.

        Args:
            request: MessageProcessingRequest con message, context, user_type
            phone: Teléfono del cliente
            normalize_profession_for_search: Función para normalizar profesión
            _normalize_token: Función para normalizar tokens

        Returns:
            MessageProcessingResponse con response, intent, entities, confidence
        """
        try:
            logger.info(
                f"📨 Procesando mensaje de cliente: {phone} - {request.message[:100]}..."
            )

            # Guardar mensaje del usuario en sesión
            await self.session_manager.save_session(
                phone, request.message, is_bot=False
            )

            # Obtener contexto de conversación para extracción
            conversation_context = await self.session_manager.get_session_context(phone)

            # Extraer profesión y ubicación usando el método simple
            (
                detected_profession,
                detected_location,
            ) = self.extract_profession_and_location(conversation_context, request.message)
            profession = detected_profession
            location = detected_location

            if location:
                location = location.strip()

            normalized_profession_token = None
            if profession:
                normalized_profession_token = _normalize_token(profession)
                normalized_for_search = normalize_profession_for_search(profession)
                if normalized_for_search:
                    profession = normalized_for_search
                elif normalized_profession_token:
                    profession = normalized_profession_token

            # Caso 1: Tenemos profesión y ubicación - buscar proveedores
            if profession and location:
                return await self._search_and_build_response(
                    profession, location, phone, request
                )

            # Caso 2: No tenemos profesión - pedir guía
            if not profession:
                return await self._build_guidance_response(location, phone, request)

            # Caso 3: Tenemos profesión pero no ubicación - usar OpenAI
            return await self._build_openai_response(
                request, conversation_context, phone
            )

        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
            raise

    async def _search_and_build_response(
        self, profession: str, location: str, phone: str, request
    ) -> MessageProcessingResponse:
        """
        Busca proveedores y construye respuesta.

        Args:
            profession: Profesión detectada
            location: Ubicación detectada
            phone: Teléfono del cliente
            request: Request original

        Returns:
            Dict con respuesta formateada
        """
        search_payload = {
            "main_profession": profession,
            "location": location,
        }
        providers_result = await self.intelligent_search_providers_remote(search_payload)

        if not providers_result["ok"] or not providers_result["providers"]:
            providers_result = await self.search_providers(profession, location)

        if providers_result["ok"] and providers_result["providers"]:
            providers = providers_result["providers"][:3]
            lines = []
            lines.append(
                f"¡Excelente! He encontrado {len(providers)} {profession}s "
                f"en {location.title() if isinstance(location, str) else location}:"
            )
            lines.append("")
            for i, p in enumerate(providers, 1):
                name = p.get("name") or p.get("provider_name") or "Proveedor"
                rating = p.get("rating", 4.5)
                phone_out = p.get("phone") or p.get("phone_number") or "s/n"
                desc = p.get("description") or p.get("services_offered") or ""
                exp = p.get("experience") or f"{p.get('experience_years', 0)} años"
                lines.append(f"{i}. {name} ⭐{rating}")
                lines.append(f"   - Teléfono: {phone_out}")
                if exp and exp != "0 años":
                    lines.append(f"   - Experiencia: {exp}")
                if isinstance(desc, list):
                    desc = ", ".join(desc[:3])
                if desc:
                    lines.append(f"   - {desc}")
                specialty_tags = p.get("matched_terms") or p.get("specialties")
                if specialty_tags:
                    if isinstance(specialty_tags, list):
                        display = ", ".join(
                            str(item) for item in specialty_tags[:3] if str(item).strip()
                        )
                    else:
                        display = str(specialty_tags)
                    if display:
                        lines.append(f"   - Coincidencias: {display}")
                lines.append("")
            lines.append("¿Quieres que te comparta el contacto de alguno?")
            ai_response_text = "\n".join(lines)

            await self.session_manager.save_session(phone, ai_response_text, is_bot=True)

            # Registrar en Supabase
            try:
                if self.supabase:
                    self.supabase.table("service_requests").insert(
                        {
                            "phone": phone,
                            "intent": "service_request",
                            "profession": profession,
                            "location_city": location,
                            "requested_at": datetime.now(timezone.utc).isoformat(),
                            "resolved_at": datetime.now(timezone.utc).isoformat(),
                            "suggested_providers": providers,
                        }
                    ).execute()
            except Exception as e:
                logger.warning(
                    f"⚠️ No se pudo registrar service_request en Supabase: {e}"
                )

            return MessageProcessingResponse(
                response=ai_response_text,
                intent="service_request",
                entities={
                    "profession": profession,
                    "location": location,
                    "providers": providers,
                },
                confidence=0.9,
            )

        # Si no hay proveedores, retornar respuesta vacía con baja confianza
        return MessageProcessingResponse(
            response="Lo siento, no encontré proveedores disponibles en este momento.",
            intent="service_request",
            entities={"profession": profession, "location": location, "providers": []},
            confidence=0.3,
        )

    async def _build_guidance_response(
        self, location: Optional[str], phone: str, request
    ) -> MessageProcessingResponse:
        """
        Construye respuesta de guía cuando no hay profesión.

        Args:
            location: Ubicación detectada (puede ser None)
            phone: Teléfono del cliente
            request: Request original

        Returns:
            Dict con respuesta de guía
        """
        guidance_text = (
            "Estoy teniendo problemas para entender exactamente el servicio que "
            "necesitas. ¿Podrías decirlo en una palabra? Por ejemplo: marketing, "
            "publicidad, diseño, plomería."
        )
        await self.session_manager.save_session(phone, guidance_text, is_bot=True)

        return MessageProcessingResponse(
            response=guidance_text,
            intent="service_request",
            entities={
                "profession": None,
                "location": location,
            },
            confidence=0.5,
        )

    async def _build_openai_response(
        self, request, conversation_context: str, phone: str
    ) -> MessageProcessingResponse:
        """
        Construye respuesta usando OpenAI.

        Args:
            request: Request original
            conversation_context: Contexto de conversación
            phone: Teléfono del cliente

        Returns:
            Dict con respuesta de OpenAI
        """
        # Construir prompt con contexto
        context_prompt = (
            "Eres un asistente de TinkuBot, un marketplace de servicios profesionales en "
            "Ecuador. Tu rol es entender las necesidades del cliente y extraer:\n"
            "1. Tipo de servicio/profesión que necesita\n"
            "2. Ubicación (si menciona)\n"
            "3. Urgencia\n"
            "4. Presupuesto (si menciona)\n\n"
            f"CONTEXTO DE LA CONVERSACIÓN:\n{conversation_context}\n\n"
            "Responde de manera amable y profesional, siempre en español."
        )

        # Llamar a OpenAI (si hay API key). Si no, fallback básico
        if not self.openai_client:
            ai_response = (
                "Gracias por tu mensaje. Para ayudarte mejor, cuéntame el servicio que "
                "necesitas (por ejemplo, plomero, electricista) y tu ciudad."
            )
        else:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context_prompt},
                    {"role": "user", "content": request.message},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            ai_response = response.choices[0].message.content

        confidence = 0.85  # Confianza base

        # Extraer entidades básicas
        entities = {
            "profession": None,
            "location": None,
            "urgency": None,
            "budget": None,
        }

        # Detectar intenciones comunes
        intent = "information_request"
        if "necesito" in request.message.lower() or "busco" in request.message.lower():
            intent = "service_request"
        elif "precio" in request.message.lower() or "costo" in request.message.lower():
            intent = "pricing_inquiry"
        elif "disponible" in request.message.lower():
            intent = "availability_check"

        # Guardar respuesta del bot en sesión
        await self.session_manager.save_session(phone, ai_response, is_bot=True)

        logger.info(f"✅ Mensaje procesado. Intent: {intent}")

        return MessageProcessingResponse(
            response=ai_response,
            intent=intent,
            entities=entities,
            confidence=confidence,
        )
