"""Servicio de validación de proveedores con IA."""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


class ValidadorProveedoresIA:
    """
    Servicio de validación de proveedores usando IA.

    Usa OpenAI para validar que los proveedores encontrados REALMENTE
    puedan ayudar con la necesidad del usuario.
    """

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        openai_semaphore: asyncio.Semaphore,
        openai_timeout: float,
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de validación.

        Args:
            openai_client: Cliente de OpenAI
            openai_semaphore: Semaphore para limitar concurrencia
            openai_timeout: Timeout en segundos para llamadas a OpenAI
            logger: Logger para trazabilidad
        """
        self.openai_client = openai_client
        self.openai_semaphore = openai_semaphore
        self.openai_timeout = openai_timeout
        self.logger = logger

    async def validar_proveedores(
        self,
        user_need: str,
        providers: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Usa IA para validar que los proveedores encontrados REALMENTE puedan ayudar
        con la necesidad del usuario.

        Analiza tanto la profesión como los servicios de cada proveedor para determinar
        si tiene la capacidad y experiencia apropiada.

        Args:
            user_need: Necesidad del usuario (ej: "marketing", "community manager")
            providers: Lista de proveedores a validar

        Returns:
            Lista solo con los proveedores validados por la IA.
        """
        if not providers:
            return []

        if not self.openai_client:
            self.logger.warning("⚠️ validar_proveedores sin cliente OpenAI")
            return providers

        self.logger.info(
            f"🤖 Validando {len(providers)} proveedores con IA para '{user_need}'"
        )

        # Construir prompt con información completa de proveedores
        providers_info = []
        for i, p in enumerate(providers):
            # Extraer información relevante del proveedor
            # Manejar tanto "profession" (singular) como "professions" (plural lista)
            profession_raw = p.get("profession") or p.get("professions")
            if isinstance(profession_raw, list):
                profession = ", ".join(str(prof) for prof in profession_raw[:3])
            else:
                profession = str(profession_raw) if profession_raw else "N/A"

            services = p.get("services", "N/A")
            services_list = p.get("services_list", [])
            experience = p.get("experience_years") or p.get("years_of_experience", "N/A")
            rating = p.get("rating", "N/A")

            # Si services_list está disponible, usarlo, si no, usar services
            if services_list and isinstance(services_list, list):
                services_text = ", ".join(str(s) for s in services_list[:5])
            else:
                services_text = str(services)

            provider_text = f"""Proveedor {i+1}:
- Profesión: {profession}
- Servicios: {services_text}
- Experiencia: {experience} años
- Rating: {rating}"""
            providers_info.append(provider_text)

        providers_block = "\n".join(providers_info)

        system_prompt = f"""Eres un experto en servicios profesionales. Tu tarea es analizar si cada proveedor PUEDE ayudar con esta necesidad del usuario.

IMPORTANTE: Los servicios pueden estar en español o inglés. Términos como "community manager", "social media manager", "community management" son EQUIVALENTES a "gestor de redes sociales", "manejo de redes sociales", "gestión de redes sociales".

NECESIDAD DEL USUARIO: "{user_need}"

{providers_block}

Para CADA proveedor, responde si PUEDE ayudar o NO ayudar.

Criterios importantes:
1. La profesión del proveedor debe ser APROPIADA para la necesidad
   - Ejemplo: Para "contratación pública", un ABOGADO es apropiado, un MÉDICO NO lo es
   - Ejemplo: Para "marketing", un PUBLICISTA es apropiado, un PLOMERO NO lo es
   - Ejemplo: Para "gestor de redes sociales", "community manager" o "social media" son APROPIADOS

2. Los servicios que ofrece deben ser RELEVANTES y APLICABLES
   - No basta con mencionar palabras clave
   - Los servicios deben demostrar capacidad real de atender la necesidad
   - Acepta términos en inglés o español que sean equivalentes
   - "community manager" = "gestor de redes sociales" ✓
   - "social media" = "redes sociales" ✓
   - "marketing" = "mercadeo" ✓

3. La experiencia debe ser APLICABLE a la necesidad
   - No solo mencionar el término, sino tener experiencia real en ese servicio

Responde SOLO con JSON (array de booleanos, en el mismo orden):
[
  true,   // Proveedor 1: SÍ puede ayudar
  false,  // Proveedor 2: NO puede ayudar
  true,   // Proveedor 3: SÍ puede ayudar
  ...
]

NO incluyas explicaciones. Solo el array de booleanos."""

        self.logger.info(f"📋 Prompt enviado a IA de validación:\n{system_prompt[:1000]}...")

        try:
            async with self.openai_semaphore:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Eres un experto analista de servicios profesionales. Analizas si un proveedor tiene la capacidad real de ayudar con una necesidad específica basándote en su profesión y servicios.",
                            },
                            {"role": "user", "content": system_prompt},
                        ],
                        temperature=0.3,
                        max_tokens=150,
                    ),
                    timeout=self.openai_timeout,
                )

            if not response.choices:
                self.logger.warning("⚠️ OpenAI respondió sin choices en validar_proveedores")
                return providers

            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = re.sub(
                    r"^```(?:json)?", "", content, flags=re.IGNORECASE
                ).strip()
                content = re.sub(r"```$", "", content).strip()

            self.logger.debug(f"🤖 Respuesta validación IA: {content[:200]}")

            validation_list = json.loads(content)

            if not isinstance(validation_list, list):
                self.logger.warning(
                    f"⚠️ Respuesta de validación no es array: {type(validation_list)}"
                )
                return providers

            if len(validation_list) != len(providers):
                self.logger.warning(
                    f"⚠️ Respuesta IA tiene {len(validation_list)} valores, "
                    f"pero esperaba {len(providers)}"
                )
                # Ajustar longitud si es necesario
                validation_list = validation_list[: len(providers)]

            # Filtrar proveedores validados
            validated_providers = []
            for provider, is_valid in zip(providers, validation_list):
                if is_valid and isinstance(is_valid, bool) and is_valid:
                    validated_providers.append(provider)

            self.logger.info(
                f"✅ Validación IA: {len(validated_providers)}/{len(providers)} "
                f"proveedores validados para '{user_need}'"
            )

            return validated_providers

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en validar_proveedores, retornando todos")
            return providers
        except json.JSONDecodeError as exc:
            self.logger.warning(f"⚠️ Error parseando JSON validación: {exc}")
            return providers
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en validación IA, retornando todos: {exc}")
            return providers
