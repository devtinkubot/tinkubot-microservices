"""Servicio de expansión de términos de búsqueda con IA."""

import asyncio
import json
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from models.catalogo_servicios import (
    SERVICIOS_COMUNES,
    SINONIMOS_SERVICIOS_COMUNES,
)


class ExpansorSinonimos:
    """
    Servicio de expansión de términos de búsqueda usando IA.

    Genera sinónimos y términos equivalentes para mejorar la búsqueda
    de proveedores cuando la terminología varía.
    """

    # Sinónimos de ciudades de Ecuador
    SINONIMOS_CIUDADES_ECUADOR = {
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
        cliente_openai: Optional[AsyncOpenAI],
        semaforo_openai: Optional[asyncio.Semaphore],
        tiempo_espera_openai: float,
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de expansión.

        Args:
            cliente_openai: Cliente de OpenAI (opcional)
            semaforo_openai: Semaphore para limitar concurrencia
            tiempo_espera_openai: Timeout en segundos para llamadas a OpenAI
            logger: Logger para trazabilidad
        """
        self.cliente_openai = cliente_openai
        self.semaforo_openai = semaforo_openai
        self.tiempo_espera_openai = tiempo_espera_openai
        self.logger = logger

    def _normalizar_texto_para_coincidencia(self, texto: str) -> str:
        """Normaliza texto para comparación flexible."""
        base = (texto or "").lower()
        normalizado = unicodedata.normalize("NFD", base)
        sin_acentos = "".join(
            ch for ch in normalizado if unicodedata.category(ch) != "Mn"
        )
        limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
        return re.sub(r"\s+", " ", limpio).strip()

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
        texto_combinado = f"{historial_texto}\n{ultimo_mensaje}"
        texto_normalizado = self._normalizar_texto_para_coincidencia(texto_combinado)
        if not texto_normalizado:
            return None, None

        texto_con_padding = f" {texto_normalizado} "

        profesion = None
        for canonico, sinonimos in SINONIMOS_SERVICIOS_COMUNES.items():
            for sinonimo in sinonimos:
                sinonimo_normalizado = self._normalizar_texto_para_coincidencia(sinonimo)
                if not sinonimo_normalizado:
                    continue
                if f" {sinonimo_normalizado} " in texto_con_padding:
                    profesion = canonico
                    break
            if profesion:
                break

        if not profesion:
            for servicio in SERVICIOS_COMUNES:
                servicio_normalizado = self._normalizar_texto_para_coincidencia(servicio)
                if servicio_normalizado and f" {servicio_normalizado} " in texto_con_padding:
                    profesion = servicio
                    break

        ubicacion = None
        for ciudad_canonica, sinonimos in self.SINONIMOS_CIUDADES_ECUADOR.items():
            for sinonimo in sinonimos:
                sinonimo_normalizado = self._normalizar_texto_para_coincidencia(sinonimo)
                if not sinonimo_normalizado:
                    continue
                if f" {sinonimo_normalizado} " in texto_con_padding:
                    ubicacion = ciudad_canonica
                    break
            if ubicacion:
                break

        return profesion, ubicacion

    async def expandir_necesidad_con_ia(
        self,
        necesidad_usuario: str,
        max_sinonimos: int = 5,
    ) -> List[str]:
        """
        Expande una necesidad del usuario usando IA para generar sinónimos relevantes.

        Esta función llama a GPT-3.5-turbo para generar términos de búsqueda equivalentes
        en español e inglés, mejorando la capacidad de encontrar proveedores que usen
        terminología diferente.

        Args:
            necesidad_usuario: La necesidad del usuario (ej: "marketing", "community manager")
            max_sinonimos: Número máximo de sinónimos a generar (default: 5)

        Returns:
            Lista de términos expandidos incluyendo el término original.
            Si hay error, retorna [necesidad_usuario] como fallback.
        """
        if not self.cliente_openai:
            self.logger.warning("⚠️ expandir_necesidad_con_ia: sin cliente OpenAI")
            return [necesidad_usuario]

        if not necesidad_usuario or not necesidad_usuario.strip():
            return []

        self.logger.info(f"🔄 Expandiendo necesidad con IA: '{necesidad_usuario}'")

        # Truncar si es muy largo (limitar input tokens)
        necesidad_truncada = necesidad_usuario[:200].strip()

        prompt_sistema = f"""Eres un experto en servicios profesionales. Genera {max_sinonimos} términos de búsqueda que capturen:
1. La profesión/servicio principal
2. Sinónimos comunes en español
3. Términos equivalentes en inglés si aplica
4. Variedades relacionadas que usarían proveedores

Ejemplos:
- "marketing" → ["marketing", "publicidad", "mercadotecnia", "marketing digital", "promoción"]
- "gestor de redes sociales" → ["gestor de redes sociales", "community manager", "social media manager", "redes sociales"]

Responde SOLO con un JSON array de strings. Sin explicaciones."""

        prompt_usuario = (
            f'Genera {max_sinonimos} sinónimos o términos equivalentes para: "{necesidad_truncada}"'
        )

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.5,
                        max_tokens=150,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                self.logger.warning("⚠️ OpenAI respondió sin choices en expandir_necesidad_con_ia")
                return [necesidad_usuario]

            contenido = (respuesta.choices[0].message.content or "").strip()
            self.logger.debug(f"🤖 Respuesta cruda expansión IA: {contenido[:200]}")

            # Limpiar markdown code blocks si existen
            if contenido.startswith("```"):
                contenido = re.sub(
                    r"^```(?:json)?", "", contenido, flags=re.IGNORECASE
                ).strip()
                contenido = re.sub(r"```$", "", contenido).strip()

            # Parsear JSON
            try:
                lista_sinonimos = json.loads(contenido)
            except json.JSONDecodeError:
                self.logger.warning(
                    f"⚠️ No se pudo parsear JSON de expansión: {contenido[:100]}"
                )
                return [necesidad_usuario]

            # Validar que sea una lista
            if not isinstance(lista_sinonimos, list):
                self.logger.warning(
                    f"⚠️ Respuesta no es lista: {type(lista_sinonimos)}"
                )
                return [necesidad_usuario]

            # Validar y limpiar elementos
            sinonimos_validos = []
            for item in lista_sinonimos:
                if isinstance(item, str) and item.strip():
                    sinonimos_validos.append(item.strip())

            if not sinonimos_validos:
                self.logger.warning("⚠️ Lista de sinónimos vacía después de validación")
                return [necesidad_usuario]

            # Asegurar que el término original esté incluido
            if necesidad_usuario not in sinonimos_validos:
                sinonimos_validos.insert(0, necesidad_usuario)

            # Limitar a max_sinonimos
            terminos_finales = sinonimos_validos[:max_sinonimos]

            self.logger.info(
                f"✅ Expansión IA completada: '{necesidad_usuario}' → {terminos_finales}"
            )
            return terminos_finales

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en expandir_necesidad_con_ia, usando fallback")
            return [necesidad_usuario]
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en expandir_necesidad_con_ia: {exc}")
            return [necesidad_usuario]

    async def _extraer_profesion_con_ia(self, texto: str) -> Optional[str]:
        """
        Extrae la profesión/servicio del texto usando IA cuando la búsqueda estática falla.

        Esto permite detectar servicios que NO están en SINONIMOS_SERVICIOS_COMUNES,
        como "gestor de redes sociales", "community manager", etc.
        """
        if not texto or not texto.strip():
            return None

        if not self.cliente_openai:
            return None

        prompt_sistema = """Eres un experto en identificar servicios profesionales. Tu tarea es extraer EL SERVICIO PRINCIPAL que el usuario necesita.

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

        prompt_usuario = (
            f'¿Cuál es el servicio principal que necesita este usuario: "{texto[:200]}"'
        )

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.3,
                        max_tokens=50,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                return None

            profesion = (respuesta.choices[0].message.content or "").strip()
            # Limpiar comillas y otros caracteres
            profesion = profesion.strip('"').strip("'").strip()

            self.logger.info(
                f"✅ IA extrajo profesión: '{profesion}' del texto: '{texto[:50]}...'"
            )
            return profesion if profesion else None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo profesión con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo profesión con IA: {exc}")
            return None

    async def _extraer_ubicacion_con_ia(self, texto: str) -> Optional[str]:
        """
        Extrae la ciudad del texto usando IA cuando la búsqueda estática falla.
        """
        ciudades = [
            "Quito",
            "Guayaquil",
            "Cuenca",
            "Santo Domingo",
            "Manta",
            "Portoviejo",
            "Machala",
            "Durán",
            "Loja",
            "Ambato",
            "Riobamba",
            "Esmeraldas",
        ]

        ciudades_str = ", ".join(ciudades)

        if not self.cliente_openai:
            return None

        prompt_sistema = f"""Eres un experto en identificar ciudades de Ecuador. Tu tarea es extraer LA CIUDAD mencionada en el texto.

Ciudades válidas: {ciudades_str}

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

        prompt_usuario = f'¿Qué ciudad de Ecuador se menciona en: "{texto[:200]}"'

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.3,
                        max_tokens=30,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                return None

            ubicacion = (respuesta.choices[0].message.content or "").strip()
            ubicacion = ubicacion.strip('"').strip("'").strip()

            if ubicacion.lower() == "null" or not ubicacion:
                return None

            # Verificar que sea una ciudad válida
            for ciudad in ciudades:
                if ciudad.lower() == ubicacion.lower():
                    self.logger.info(
                        f"✅ IA extrajo ciudad: '{ciudad}' del texto: '{texto[:50]}...'"
                    )
                    return ciudad

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
        profesion, ubicacion = self.extraer_servicio_y_ubicacion(
            historial_texto, ultimo_mensaje
        )

        # Paso 2: Si no hay profesión, usar IA para extraer del texto
        if not profesion and self.cliente_openai:
            self.logger.info(f"🤖 Extracción estática falló, usando IA para: '{ultimo_mensaje[:100]}...'")
            profesion = await self._extraer_profesion_con_ia(ultimo_mensaje)

            # Intentar extraer ubicación también con IA
            if not ubicacion:
                ubicacion = await self._extraer_ubicacion_con_ia(ultimo_mensaje)

        # Paso 3: Si aún no hay profesión, retornar None
        if not profesion:
            return None, None, None

        # Paso 4: Expandir usando IA (siempre que tengamos profesión)
        try:
            terminos_expandidos = await self.expandir_necesidad_con_ia(
                profesion, max_sinonimos=5
            )
            return profesion, ubicacion, terminos_expandidos
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en wrapper con expansión: {exc}")
            # Fallback: retornar solo el término original
            return profesion, ubicacion, [profesion]
