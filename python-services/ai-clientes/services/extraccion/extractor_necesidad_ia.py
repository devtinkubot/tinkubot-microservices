"""Extractor de necesidad y ciudad usando IA."""

import asyncio
import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from config.configuracion import configuracion
from utils.texto import normalizar_texto_para_coincidencia


class ExtractorNecesidadIA:
    """Servicio de extracción semántica de servicio y ciudad con IA."""

    # Modelos desde configuración centralizada
    MODELO_EXTRACCION = configuracion.modelo_extraccion
    MODELO_NORMALIZACION = configuracion.modelo_normalizacion

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

    async def _normalizar_servicio_a_espanol(
        self, servicio_detectado: str
    ) -> Optional[str]:
        """Normaliza un servicio detectado a español neutro usando IA."""
        if not self.cliente_openai:
            return servicio_detectado

        servicio_base = (servicio_detectado or "").strip()
        if not servicio_base:
            return servicio_detectado

        prompt_sistema = """Convierte nombres de servicios profesionales a español neutro.

Reglas:
- Si ya está en español, devuélvelo en español neutro.
- Si está en otro idioma, tradúcelo al español.
- Devuelve una frase breve (2 a 5 palabras), en minúsculas.
- No agregues explicaciones.

Responde SOLO con el nombre del servicio."""

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_NORMALIZACION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": servicio_base[:120]},
                        ],
                        temperature=0.0,
                        max_tokens=40,
                    ),
                    timeout=self.tiempo_espera_openai,
                )
            if not respuesta.choices:
                return servicio_detectado

            servicio_es = (respuesta.choices[0].message.content or "").strip()
            servicio_es = servicio_es.strip('"').strip("'").strip()
            return servicio_es or servicio_detectado
        except Exception as exc:
            self.logger.warning(f"⚠️ Error normalizando servicio a español: {exc}")
            return servicio_detectado

    async def extraer_servicio_con_ia(self, mensaje_usuario: str) -> Optional[str]:
        """Extrae el servicio requerido por el cliente usando IA."""
        if not self.cliente_openai:
            self.logger.warning("⚠️ extraer_servicio_con_ia: sin cliente OpenAI")
            return None

        if not mensaje_usuario or not mensaje_usuario.strip():
            return None

        prompt_sistema = """Eres un experto en servicios profesionales en Ecuador. Identifica el servicio que necesita el usuario y devuelve el NOMBRE ESTÁNDAR del servicio en español.

MAPEOS DE TERMINOLOGÍA COLOQUIAL A SERVICIOS ESTÁNDAR:
- "maneja redes sociales", "manejo de redes", "redes sociales", "community manager" → "gestión de redes sociales"
- "bug en página web", "error en web", "página no funciona" → "desarrollo web"
- "error en app", "aplicación falla", "mi app no abre" → "desarrollo de aplicaciones"
- "problema con base de datos", "bd lenta", "datos corruptos" → "administración de base de datos"
- "diseño de logo", "hacer un logo", "necesito un logo" → "diseño gráfico"
- "fotos de producto", "sesión de fotos", "fotografía" → "fotografía"
- "video promocional", "edición de video", "hacer un video" → "edición de video"
- "traducir documentos", "traducción", "traductor" → "traducción"
- "asesoría legal", "problema legal", "abogado" → "asesoría legal"
- "contabilidad", "impuestos", "declaración de renta" → "contabilidad"
- "marketing digital", "publicidad en internet", "anuncios" → "marketing digital"
- "posicionar en google", "seo", "aparecer en búsquedas" → "posicionamiento web"
- "campañas publicitarias", "anuncios facebook", "ads" → "publicidad digital"

REGLAS CRÍTICAS:
1. Devuelve SIEMPRE el nombre del servicio en minúsculas y en español
2. Usa el formato más estándar y común (2 a 5 palabras)
3. NUNCA uses términos en inglés como "community manager", "seo", "ads"
4. Si el usuario escribe en otro idioma, traduce al español neutro

Responde SOLO con el nombre del servicio, sin explicaciones."""

        prompt_usuario = (
            f'¿Qué servicio necesita este usuario: "{mensaje_usuario[:200]}"'
        )

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_EXTRACCION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.1,
                        max_tokens=30,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                return None

            servicio = (respuesta.choices[0].message.content or "").strip()
            servicio = servicio.strip('"').strip("'").strip()

            servicio = await self._normalizar_servicio_a_espanol(servicio)

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
                        model=self.MODELO_NORMALIZACION,
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
