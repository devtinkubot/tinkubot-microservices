"""Extractor de necesidad y ciudad usando IA."""

import asyncio
import logging
import re
import unicodedata
from typing import Optional

from openai import AsyncOpenAI


class ExtractorNecesidadIA:
    """Servicio de extracción semántica de servicio y ciudad con IA."""

    # Sinónimos de ciudades de Ecuador para normalización local
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

    async def extraer_servicio_con_ia(self, mensaje_usuario: str) -> Optional[str]:
        """Extrae el servicio requerido por el cliente usando IA."""
        if not self.cliente_openai:
            self.logger.warning("⚠️ extraer_servicio_con_ia: sin cliente OpenAI")
            return None

        if not mensaje_usuario or not mensaje_usuario.strip():
            return None

        prompt_sistema = """Eres un experto en servicios profesionales. Tu tarea es identificar el servicio que necesita el usuario.

IMPORTANTE:
- No estás limitado a una lista predefinida de servicios
- Detecta el servicio más específico posible
- Si el usuario menciona "bug en página web", responde "desarrollador web"
- Si menciona "error en app", responde "desarrollador de aplicaciones"
- Si menciona "problema con base de datos", responde "administrador de base de datos"
- Términos en inglés como "community manager" o "developer" son válidos

Responde SOLO con el nombre del servicio, sin explicaciones."""

        prompt_usuario = (
            f'¿Qué servicio necesita este usuario: "{mensaje_usuario[:200]}"'
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

            servicio = (respuesta.choices[0].message.content or "").strip()
            servicio = servicio.strip('"').strip("'").strip()

            self.logger.info(
                "✅ IA detectó servicio: '%s' de: '%s...'",
                servicio,
                mensaje_usuario[:50],
            )
            return servicio if servicio else None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo servicio con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo servicio con IA: {exc}")
            return None

    async def extraer_servicio_con_ia_pura(
        self,
        mensaje_usuario: str,
    ) -> Optional[str]:
        """Alias de compatibilidad para extraer servicio con IA."""
        return await self.extraer_servicio_con_ia(mensaje_usuario)

    async def extraer_ubicacion_con_ia(self, texto: str) -> Optional[str]:
        """Extrae la ciudad del texto usando IA."""
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

            for ciudad in ciudades:
                if ciudad.lower() == ubicacion.lower():
                    self.logger.info(
                        "✅ IA extrajo ciudad: '%s' del texto: '%s...'",
                        ciudad,
                        texto[:50],
                    )
                    return ciudad

            return None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo ciudad con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo ciudad con IA: {exc}")
            return None

    async def _extraer_ubicacion_con_ia(self, texto: str) -> Optional[str]:
        """Alias de compatibilidad para extracción de ciudad con IA."""
        return await self.extraer_ubicacion_con_ia(texto)
