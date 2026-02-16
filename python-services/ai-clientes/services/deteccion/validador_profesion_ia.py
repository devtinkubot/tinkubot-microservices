"""Detector de intención de profesión usando IA."""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from config.configuracion import configuracion


@dataclass
class ResultadoDeteccionProfesion:
    """Resultado de la detección de intención de profesión."""

    es_profesion: bool
    confianza: float  # 0.0 a 1.0


PROMPT_DETECCION_PROFESION = """Eres un experto en análisis de intención de búsqueda de servicios.

Tu tarea es detectar si el usuario está:
A) Pidiendo un PROFESIONAL (ej: "busco médico", "necesito abogado", "quiero un plomero")
B) Describiendo un PROBLEMA/NECESIDAD (ej: "tengo dolor de espalda", "mi tubería gotea", "necesito revisar un contrato")

REGLAS:
- "médico", "doctor", "abogado", "ingeniero", "arquitecto", "plomero", "electricista", "carpintero", "mecánico" = PROFESIÓN
- Si el usuario menciona la profesión SIN describir el problema = PROFESIÓN
- Si el usuario describe síntomas, necesidades, problemas = NO ES PROFESIÓN (aunque mencione la profesión)
- "necesito un médico para dolor de espalda" = NO ES PROFESIÓN (tiene descripción del problema)
- "busco médico" = ES PROFESIÓN (sin descripción del problema)
- Frases como "busco un...", "necesito un...", "quiero contratar un..." + profesión SIN problema = PROFESIÓN

Responde SOLO con JSON:
{
  "es_profesion": true/false,
  "confianza": 0.0-1.0
}"""


class ValidadorProfesionIA:
    """
    Servicio de detección de intención de profesión usando IA.

    Detecta cuando un usuario está pidiendo un profesional directamente
    en lugar de describir su problema/necesidad.
    """

    # Configuración vía variables de entorno
    MODELO = (
        os.getenv("DETECCION_PROFESION_MODELO")
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )
    TIMEOUT = float(os.getenv("DETECCION_PROFESION_TIMEOUT", "5"))
    UMBRAL_CONFIANZA = float(os.getenv("DETECCION_PROFESION_UMBRAL", "0.7"))

    def __init__(
        self,
        cliente_openai: Optional[AsyncOpenAI],
        semaforo_openai: Optional[asyncio.Semaphore],
        tiempo_espera_openai: float,
        logger: logging.Logger,
    ):
        """
        Inicializar el detector de profesión.

        Args:
            cliente_openai: Cliente de OpenAI
            semaforo_openai: Semaphore para limitar concurrencia
            tiempo_espera_openai: Timeout en segundos para llamadas a OpenAI
            logger: Logger para trazabilidad
        """
        self.cliente_openai = cliente_openai
        self.semaforo_openai = semaforo_openai
        self.tiempo_espera_openai = tiempo_espera_openai
        self.logger = logger

    async def detectar_intencion_profesion(
        self,
        texto: str,
    ) -> Optional[ResultadoDeteccionProfesion]:
        """
        Detecta si el usuario está pidiendo un profesional o describiendo un problema.

        Args:
            texto: Texto del mensaje del usuario

        Returns:
            ResultadoDeteccionProfesion con es_profesion y confianza,
            o None si hubo error (fail-safe: pedir detalles)
        """
        if not self.cliente_openai or not self.semaforo_openai:
            self.logger.warning("⚠️ detectar_intencion_profesion: sin cliente OpenAI")
            # Fail-safe: retornar None para pedir detalles
            return None

        if not texto or not texto.strip():
            return ResultadoDeteccionProfesion(es_profesion=False, confianza=1.0)

        texto_limpio = texto.strip()[:300]  # Limitar longitud

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO,
                        messages=[
                            {"role": "system", "content": PROMPT_DETECCION_PROFESION},
                            {"role": "user", "content": texto_limpio},
                        ],
                        temperature=0.0,
                        max_tokens=50,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                self.logger.warning(
                    "⚠️ detectar_intencion_profesion: OpenAI respondió sin choices"
                )
                return None

            contenido = (respuesta.choices[0].message.content or "").strip()

            # Limpiar formato markdown si existe
            if contenido.startswith("```"):
                contenido = re.sub(
                    r"^```(?:json)?", "", contenido, flags=re.IGNORECASE
                ).strip()
                contenido = re.sub(r"```$", "", contenido).strip()

            datos = json.loads(contenido)

            es_profesion = bool(datos.get("es_profesion", False))
            confianza = float(datos.get("confianza", 0.0))
            # Normalizar confianza a rango 0-1
            confianza = max(0.0, min(1.0, confianza))

            self.logger.info(
                f"✅ Detección profesión: es_profesion={es_profesion}, "
                f"confianza={confianza:.2f} para: '{texto_limpio[:50]}...'"
            )

            return ResultadoDeteccionProfesion(
                es_profesion=es_profesion,
                confianza=confianza,
            )

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en detectar_intencion_profesion")
            # Fail-safe: retornar None para pedir detalles
            return None
        except json.JSONDecodeError as exc:
            self.logger.warning(f"⚠️ Error parseando JSON detección profesión: {exc}")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en detectar_intencion_profesion: {exc}")
            return None
