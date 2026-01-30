"""Servicio de expansión de términos de búsqueda con IA."""

import asyncio
import json
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from models.catalogo_servicios import (
    COMMON_SERVICE_SYNONYMS,
    COMMON_SERVICES,
)


class ExpansorSinonimos:
    """
    Servicio de expansión de términos de búsqueda usando IA.

    Genera sinónimos y términos equivalentes para mejorar la búsqueda
    de proveedores cuando la terminología varía.
    """

    # Sinónimos de ciudades de Ecuador
    ECUADOR_CITY_SYNONYMS = {
        "Quito": {"quito"},
        "Guayaquil": {"guayaquil"},
        "Cuenca": {"cuenca", "cueca"},
        "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
        "Manta": {"manta"},
        "Portoviejo": {"portoviejo"},
        "Machala": {"machala"},
        "Durán": {"duran", "durán"},
        "Loja": {"loja"},
        "Ambato": {"ambato"},
        "Riobamba": {"riobamba"},
        "Esmeraldas": {"esmeraldas"},
        "Quevedo": {"quevedo"},
        "Babahoyo": {"babahoyo", "baba hoyo"},
        "Milagro": {"milagro"},
        "Ibarra": {"ibarra"},
        "Tulcán": {"tulcan", "tulcán"},
        "Latacunga": {"latacunga"},
        "Salinas": {"salinas"},
    }

    def __init__(
        self,
        openai_client: Optional[AsyncOpenAI],
        openai_semaphore: Optional[asyncio.Semaphore],
        openai_timeout: float,
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de expansión.

        Args:
            openai_client: Cliente de OpenAI (opcional)
            openai_semaphore: Semaphore para limitar concurrencia
            openai_timeout: Timeout en segundos para llamadas a OpenAI
            logger: Logger para trazabilidad
        """
        self.openai_client = openai_client
        self.openai_semaphore = openai_semaphore
        self.openai_timeout = openai_timeout
        self.logger = logger

    def _normalize_text_for_matching(self, text: str) -> str:
        """Normaliza texto para comparación flexible."""
        base = (text or "").lower()
        normalized = unicodedata.normalize("NFD", base)
        without_accents = "".join(
            ch for ch in normalized if unicodedata.category(ch) != "Mn"
        )
        cleaned = re.sub(r"[^a-z0-9\s]", " ", without_accents)
        return re.sub(r"\s+", " ", cleaned).strip()

    def extraer_servicio_y_ubicacion(
        self,
        historial_texto: str,
        ultimo_mensaje: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrae servicio y ubicación del texto usando búsqueda estática.

        Args:
            historial_texto: Historial de conversación
            ultimo_mensaje: Último mensaje del usuario

        Returns:
            Tupla (servicio, ubicacion) - puede ser (None, None)
        """
        combined_text = f"{historial_texto}\n{ultimo_mensaje}"
        normalized_text = self._normalize_text_for_matching(combined_text)
        if not normalized_text:
            return None, None

        padded_text = f" {normalized_text} "

        profession = None
        for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
            for synonym in synonyms:
                normalized_synonym = self._normalize_text_for_matching(synonym)
                if not normalized_synonym:
                    continue
                if f" {normalized_synonym} " in padded_text:
                    profession = canonical
                    break
            if profession:
                break

        if not profession:
            for service in COMMON_SERVICES:
                normalized_service = self._normalize_text_for_matching(service)
                if normalized_service and f" {normalized_service} " in padded_text:
                    profession = service
                    break

        location = None
        for canonical_city, synonyms in self.ECUADOR_CITY_SYNONYMS.items():
            for synonym in synonyms:
                normalized_synonym = self._normalize_text_for_matching(synonym)
                if not normalized_synonym:
                    continue
                if f" {normalized_synonym} " in padded_text:
                    location = canonical_city
                    break
            if location:
                break

        return profession, location

    async def expandir_necesidad_con_ia(
        self,
        user_need: str,
        max_sinonimos: int = 5,
    ) -> List[str]:
        """
        Expande una necesidad del usuario usando IA para generar sinónimos relevantes.

        Esta función llama a GPT-3.5-turbo para generar términos de búsqueda equivalentes
        en español e inglés, mejorando la capacidad de encontrar proveedores que usen
        terminología diferente.

        Args:
            user_need: La necesidad del usuario (ej: "marketing", "community manager")
            max_sinonimos: Número máximo de sinónimos a generar (default: 5)

        Returns:
            Lista de términos expandidos incluyendo el término original.
            Si hay error, retorna [user_need] como fallback.
        """
        if not self.openai_client:
            self.logger.warning("⚠️ expandir_necesidad_con_ia: sin cliente OpenAI")
            return [user_need]

        if not user_need or not user_need.strip():
            return []

        self.logger.info(f"🔄 Expandiendo necesidad con IA: '{user_need}'")

        # Truncar si es muy largo (limitar input tokens)
        need_truncated = user_need[:200].strip()

        system_prompt = f"""Eres un experto en servicios profesionales. Genera {max_sinonimos} términos de búsqueda que capturen:
1. La profesión/servicio principal
2. Sinónimos comunes en español
3. Términos equivalentes en inglés si aplica
4. Variedades relacionadas que usarían proveedores

Ejemplos:
- "marketing" → ["marketing", "publicidad", "mercadotecnia", "marketing digital", "promoción"]
- "gestor de redes sociales" → ["gestor de redes sociales", "community manager", "social media manager", "redes sociales"]

Responde SOLO con un JSON array de strings. Sin explicaciones."""

        user_prompt = f'Genera {max_sinonimos} sinónimos o términos equivalentes para: "{need_truncated}"'

        try:
            async with self.openai_semaphore:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.5,
                        max_tokens=150,
                    ),
                    timeout=self.openai_timeout,
                )

            if not response.choices:
                self.logger.warning("⚠️ OpenAI respondió sin choices en expandir_necesidad_con_ia")
                return [user_need]

            content = (response.choices[0].message.content or "").strip()
            self.logger.debug(f"🤖 Respuesta cruda expansión IA: {content[:200]}")

            # Limpiar markdown code blocks si existen
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
                content = re.sub(r"```$", "", content).strip()

            # Parsear JSON
            try:
                synonyms_list = json.loads(content)
            except json.JSONDecodeError:
                self.logger.warning(f"⚠️ No se pudo parsear JSON de expansión: {content[:100]}")
                return [user_need]

            # Validar que sea una lista
            if not isinstance(synonyms_list, list):
                self.logger.warning(f"⚠️ Respuesta no es lista: {type(synonyms_list)}")
                return [user_need]

            # Validar y limpiar elementos
            valid_synonyms = []
            for item in synonyms_list:
                if isinstance(item, str) and item.strip():
                    valid_synonyms.append(item.strip())

            if not valid_synonyms:
                self.logger.warning("⚠️ Lista de sinónimos vacía después de validación")
                return [user_need]

            # Asegurar que el término original esté incluido
            if user_need not in valid_synonyms:
                valid_synonyms.insert(0, user_need)

            # Limitar a max_sinonimos
            final_terms = valid_synonyms[:max_sinonimos]

            self.logger.info(
                f"✅ Expansión IA completada: '{user_need}' → {final_terms}"
            )
            return final_terms

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en expandir_necesidad_con_ia, usando fallback")
            return [user_need]
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en expandir_necesidad_con_ia: {exc}")
            return [user_need]

    async def _extraer_profesion_con_ia(self, text: str) -> Optional[str]:
        """
        Extrae la profesión/servicio del texto usando IA cuando la búsqueda estática falla.

        Esto permite detectar servicios que NO están en COMMON_SERVICE_SYNONYMS,
        como "gestor de redes sociales", "community manager", etc.
        """
        if not text or not text.strip():
            return None

        if not self.openai_client:
            return None

        system_prompt = """Eres un experto en identificar servicios profesionales. Tu tarea es extraer EL SERVICIO PRINCIPAL que el usuario necesita.

Reglas:
1. Responde SOLO con el nombre del servicio/profesión en español
2. Si mencionan múltiples servicios, extrae el PRINCIPAL
3. Usa términos estándar (ej: "community manager" en lugar de "gestor de redes")
4. Si no está claro qué servicio necesitan, responde con el texto más relevante

Ejemplos:
- "necesito un gestor de redes sociales" → "community manager"
- "quiero marketing" → "marketing"
- "busco abogado" → "abogado"
- "necesito alguien que me diseñe un logo" → "diseñador gráfico"

Responde SOLO con el nombre del servicio, sin explicaciones."""

        user_prompt = f'¿Cuál es el servicio principal que necesita este usuario: "{text[:200]}"'

        try:
            async with self.openai_semaphore:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.3,
                        max_tokens=50,
                    ),
                    timeout=self.openai_timeout,
                )

            if not response.choices:
                return None

            profession = (response.choices[0].message.content or "").strip()
            # Limpiar comillas y otros caracteres
            profession = profession.strip('"').strip("'").strip()

            self.logger.info(f"✅ IA extrajo profesión: '{profession}' del texto: '{text[:50]}...'")
            return profession if profession else None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo profesión con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo profesión con IA: {exc}")
            return None

    async def _extraer_ubicacion_con_ia(self, text: str) -> Optional[str]:
        """
        Extrae la ciudad del texto usando IA cuando la búsqueda estática falla.
        """
        cities = ["Quito", "Guayaquil", "Cuenca", "Santo Domingo", "Manta", "Portoviejo",
                  "Machala", "Durán", "Loja", "Ambato", "Riobamba", "Esmeraldas"]

        cities_str = ", ".join(cities)

        if not self.openai_client:
            return None

        system_prompt = f"""Eres un experto en identificar ciudades de Ecuador. Tu tarea es extraer LA CIUDAD mencionada en el texto.

Ciudades válidas: {cities_str}

Reglas:
1. Responde SOLO con el nombre de la ciudad si está en la lista
2. Si no se menciona ninguna ciudad válida, responde "null"
3. Normaliza el nombre (ej: "quito" → "Quito")

Ejemplos:
- "en Quito" → "Quito"
- "lo necesito en cuenca" → "Cuenca"
- "para guayaquil" → "Guayaquil"
- "en mi ciudad" → "null"

Responde SOLO con el nombre de la ciudad o "null", sin explicaciones."""

        user_prompt = f'¿Qué ciudad de Ecuador se menciona en: "{text[:200]}"'

        try:
            async with self.openai_semaphore:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.3,
                        max_tokens=30,
                    ),
                    timeout=self.openai_timeout,
                )

            if not response.choices:
                return None

            location = (response.choices[0].message.content or "").strip()
            location = location.strip('"').strip("'").strip()

            if location.lower() == "null" or not location:
                return None

            # Verificar que sea una ciudad válida
            for city in cities:
                if city.lower() == location.lower():
                    self.logger.info(f"✅ IA extrajo ciudad: '{city}' del texto: '{text[:50]}...'")
                    return city

            return None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo ciudad con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo ciudad con IA: {exc}")
            return None

    async def extraer_servicio_y_ubicacion_con_expansion(
        self,
        historial_texto: str,
        ultimo_mensaje: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[List[str]]]:
        """
        Wrapper que combina extracción original + extracción IA + expansión IA.

        Estrategia:
        1. Intentar extracción estática (rápida, sin IA)
        2. Si falla, usar IA para extraer profesión del texto
        3. Siempre expandir con IA para generar sinónimos

        Args:
            historial_texto: Historial de conversación
            ultimo_mensaje: Último mensaje del usuario

        Returns:
            Tupla de 3 valores:
            - profession: Profesión extraída (canónica) o None
            - location: Ciudad extraída (canónica) o None
            - expanded_terms: Lista de términos expandidos por IA o None
        """
        # Paso 1: Intentar extracción estática primero (rápida)
        profession, location = self.extraer_servicio_y_ubicacion(
            historial_texto, ultimo_mensaje
        )

        # Paso 2: Si no hay profesión, usar IA para extraer del texto
        if not profession and self.openai_client:
            self.logger.info(f"🤖 Extracción estática falló, usando IA para: '{ultimo_mensaje[:100]}...'")
            profession = await self._extraer_profesion_con_ia(ultimo_mensaje)

            # Intentar extraer ubicación también con IA
            if not location:
                location = await self._extraer_ubicacion_con_ia(ultimo_mensaje)

        # Paso 3: Si aún no hay profesión, retornar None
        if not profession:
            return None, None, None

        # Paso 4: Expandir usando IA (siempre que tengamos profesión)
        try:
            expanded_terms = await self.expandir_necesidad_con_ia(profession, max_sinonimos=5)
            return profession, location, expanded_terms
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en wrapper con expansión: {exc}")
            # Fallback: retornar solo el término original
            return profession, location, [profession]
