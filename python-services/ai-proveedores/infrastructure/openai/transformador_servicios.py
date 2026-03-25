"""
Transformador de títulos profesionales a servicios usando OpenAI.

Este módulo utiliza GPT-4o con Structured Outputs para transformar
títulos profesionales y descripciones genéricas en servicios específicos
y optimizados para búsquedas semánticas.

Características:
- Transforma "ingeniero de sistemas" → "desarrollo de software"
- Transforma "plomero" → "instalación de tuberías, reparación de fugas"
- Mantiene consistencia con JSON schema estricto
- Funciona para cualquier tipo de proveedor de servicios
"""

import json
import logging
import os
import re
from typing import List, Optional

from config.configuracion import configuracion
from openai import AsyncOpenAI
from services.shared import (
    construir_prompt_sistema_transformacion_servicios,
    construir_prompt_usuario_transformacion_servicios,
)

MAX_SERVICES = 10

logger = logging.getLogger(__name__)

_VERBOS_SENSIBLES = {
    "configuracion": {"instalacion", "instalar"},
    "configurar": {"instalacion", "instalar"},
    "reparacion": {"instalacion", "instalar", "mantenimiento"},
    "reparar": {"instalacion", "instalar", "mantenimiento"},
    "desarrollo": {"instalacion", "instalar", "soporte"},
    "desarrollar": {"instalacion", "instalar", "soporte"},
}

_CONECTORES_DIVISION = re.compile(r"\s*(?:;|/|\n)\s*")


class TransformadorServicios:
    """
    Transformador de títulos profesionales a servicios optimizados.

    Usa OpenAI GPT-4o-mini con structured outputs para garantizar respuestas
    en formato JSON consistente, optimizadas para embeddings y búsquedas.
    """

    # Modelo configurable vía env para transformación (NO embeddings)
    MODELO_TRANSFORMACION = (
        os.getenv("MODELO_TRANSFORMACION_IA") or configuracion.openai_chat_model
    )

    def __init__(self, cliente_openai: AsyncOpenAI, modelo: Optional[str] = None):
        """
        Inicializa el transformador de servicios.

        Args:
            cliente_openai: Cliente asíncrono de OpenAI
            modelo: Modelo a usar (default: desde env o configuración)
        """
        self.client = cliente_openai
        self.model = modelo or self.MODELO_TRANSFORMACION

    async def transformar_a_servicios(
        self,
        entrada_usuario: str,
        max_servicios: int = MAX_SERVICES,
    ) -> Optional[List[str]]:
        """
        Transforma entrada de usuario en lista de servicios optimizados.

        Args:
            entrada_usuario: Texto del usuario (ej: "ingeniero de sistemas, plomería")
            max_servicios: Máximo de servicios a extraer.

        Returns:
            Lista de servicios optimizados, o None si falló

        Ejemplo:
            >>> entrada = "ingeniero de sistemas, ethical hacking, desarrollo apps"
            >>> servicios = await transformador.transformar_a_servicios(entrada)
            >>> print(servicios)
            ["desarrollo de software", "pruebas de penetración",
             "auditoría de seguridad", "desarrollo de aplicaciones móviles"]
        """
        if not entrada_usuario or not entrada_usuario.strip():
            logger.warning("⚠️ Entrada vacía, no se puede transformar")
            return None

        try:
            logger.info(
                "🔄 Transformando entrada a servicios: %s...",
                entrada_usuario[:50],
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": construir_prompt_sistema_transformacion_servicios(
                            configuracion.pais_operativo
                        ),
                    },
                    {
                        "role": "user",
                        "content": construir_prompt_usuario_transformacion_servicios(
                            entrada_usuario,
                            max_servicios,
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extraccion_servicios",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "servicios": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": (
                                        "Lista de servicios específicos extraídos"
                                    ),
                                }
                            },
                            "required": ["servicios"],
                            "additionalProperties": False,
                        },
                    },
                },
                temperature=configuracion.openai_temperature_consistente,
                timeout=configuracion.openai_transform_timeout_seconds,
            )

            # Extraer JSON de la respuesta
            contenido = response.choices[0].message.content
            if not contenido:
                logger.error("❌ Respuesta de OpenAI vacía")
                return None

            datos = json.loads(contenido)
            servicios = datos.get("servicios", [])

            if not servicios:
                logger.warning("⚠️ No se extrajeron servicios de la respuesta")
                return None

            servicios = _normalizar_y_limitar_servicios(
                servicios,
                max_servicios,
                entrada_usuario=entrada_usuario,
            )
            if not servicios:
                logger.warning("⚠️ Servicios inválidos tras normalización")
                return None

            logger.info(
                "✅ Transformación exitosa: %s servicios extraídos",
                len(servicios),
            )
            for idx, servicio in enumerate(servicios, 1):
                logger.debug(f"  {idx}. {servicio}")

            return servicios

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON de OpenAI: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error transformando servicios: {e}")
            return None


def _crear_prompt_sistema() -> str:
    """Compatibilidad con tests y consumidores internos."""
    return construir_prompt_sistema_transformacion_servicios(
        configuracion.pais_operativo
    )


def _crear_prompt_usuario(entrada: str, max_servicios: int) -> str:
    """Compatibilidad con tests y consumidores internos."""
    return construir_prompt_usuario_transformacion_servicios(
        entrada,
        max_servicios,
    )


def _tokenizar_texto(texto: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-záéíóúñ]+", (texto or "").lower())
        if len(token) >= 4
    }


def _cantidad_servicios_declarados(entrada_usuario: str) -> int:
    segmentos = [
        segmento.strip()
        for segmento in _CONECTORES_DIVISION.split(entrada_usuario or "")
        if segmento.strip()
    ]
    return max(1, len(segmentos))


def _es_sobre_expansion(
    entrada_usuario: str,
    servicios: List[str],
    max_servicios: int,
) -> bool:
    limite_razonable = min(
        max_servicios,
        _cantidad_servicios_declarados(entrada_usuario),
    )
    return len(servicios) > limite_razonable


def _tiene_cambio_verbo_sensible(entrada_usuario: str, servicio: str) -> bool:
    entrada_tokens = _tokenizar_texto(entrada_usuario)
    servicio_tokens = _tokenizar_texto(servicio)
    for verbo_entrada, verbos_prohibidos in _VERBOS_SENSIBLES.items():
        if verbo_entrada in entrada_tokens and servicio_tokens.intersection(
            verbos_prohibidos
        ):
            return True
    return False


def _ajustar_frase_natural(servicio: str) -> str:
    texto = " ".join((servicio or "").strip().split())
    reemplazos = {
        "desarrollo software": "desarrollo de software",
        "desarrollo software a medida": "desarrollo de software a medida",
        "automatizacion procesos negocio": "automatización de procesos de negocio",
        "desarrollo aplicaciones moviles": "desarrollo de aplicaciones móviles",
        "configuracion redes": "configuración de redes",
        "instalacion internet": "instalación de internet",
        "servicios cableado estructurado": "cableado estructurado",
    }
    texto_min = texto.lower()
    if texto_min in reemplazos:
        return reemplazos[texto_min]
    return texto


def _servicios_fallback_desde_entrada(
    entrada_usuario: str,
    max_servicios: int,
) -> List[str]:
    segmentos = [
        _ajustar_frase_natural(segmento.strip())
        for segmento in _CONECTORES_DIVISION.split(entrada_usuario or "")
        if segmento.strip()
    ]
    resultado: List[str] = []
    for segmento in segmentos:
        texto = segmento.strip()
        if not texto:
            continue
        texto = re.sub(r"^(servicios?\s+de\s+)", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"^(servicios?\s+)", "", texto, flags=re.IGNORECASE)
        texto = texto.strip().lower()
        if texto and texto not in resultado:
            resultado.append(texto)
        if len(resultado) >= max_servicios:
            break
    return resultado


def _normalizar_y_limitar_servicios(
    servicios: List[str],
    max_servicios: int,
    *,
    entrada_usuario: str,
) -> List[str]:
    """
    Normaliza, deduplica y limita la lista final de servicios.

    Este paso es defensivo: incluso si el modelo excede el límite pedido,
    la salida se recorta a max_servicios.
    """
    resultado: List[str] = []

    servicios_postprocesados = [
        _ajustar_frase_natural(str(servicio)) for servicio in servicios
    ]
    if _es_sobre_expansion(entrada_usuario, servicios_postprocesados, max_servicios):
        logger.info("↩️ Ajustando sobre-expansión de servicios hacia entrada original")
        servicios_postprocesados = _servicios_fallback_desde_entrada(
            entrada_usuario,
            max_servicios,
        )

    for servicio in servicios_postprocesados:
        texto = str(servicio).strip()
        if _tiene_cambio_verbo_sensible(entrada_usuario, texto):
            logger.info(
                (
                    "↩️ Rechazando servicio por cambio semántico sensible: "
                    "entrada='%s' servicio='%s'"
                ),
                entrada_usuario[:120],
                texto,
            )
            continue
        if not texto or texto in resultado:
            continue
        resultado.append(texto)
        if len(resultado) >= max_servicios:
            break

    if not resultado:
        resultado = _servicios_fallback_desde_entrada(entrada_usuario, max_servicios)

    return resultado


# Función auxiliar para usar directamente sin instanciar la clase
async def transformar_texto_a_servicios(
    entrada: str,
    cliente_openai: AsyncOpenAI,
    modelo: Optional[str] = None,
    max_servicios: int = MAX_SERVICES,
) -> Optional[List[str]]:
    """
    Función de conveniencia para transformar texto a servicios.

    Args:
        entrada: Texto del usuario
        cliente_openai: Cliente de OpenAI
        modelo: Modelo a usar (default: desde env o configuración)
        max_servicios: Máximo de servicios

    Returns:
        Lista de servicios o None
    """
    transformador = TransformadorServicios(cliente_openai, modelo)
    return await transformador.transformar_a_servicios(entrada, max_servicios)
