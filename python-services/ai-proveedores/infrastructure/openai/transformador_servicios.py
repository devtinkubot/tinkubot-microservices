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
from typing import List, Optional
from openai import AsyncOpenAI

from config.configuracion import configuracion
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS

logger = logging.getLogger(__name__)


class TransformadorServicios:
    """
    Transformador de títulos profesionales a servicios optimizados.

    Usa OpenAI GPT-4o-mini con structured outputs para garantizar respuestas
    en formato JSON consistente, optimizadas para embeddings y búsquedas.
    """

    # Modelo configurable vía env para transformación (NO embeddings)
    MODELO_TRANSFORMACION = (
        os.getenv("MODELO_TRANSFORMACION_IA")
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )

    def __init__(self, cliente_openai: AsyncOpenAI, modelo: Optional[str] = None):
        """
        Inicializa el transformador de servicios.

        Args:
            cliente_openai: Cliente asíncrono de OpenAI
            modelo: Modelo a usar (default: desde env o gpt-4o-mini)
        """
        self.client = cliente_openai
        self.model = modelo or self.MODELO_TRANSFORMACION

    async def transformar_a_servicios(
        self,
        entrada_usuario: str,
        max_servicios: int = SERVICIOS_MAXIMOS,
    ) -> Optional[List[str]]:
        """
        Transforma entrada de usuario en lista de servicios optimizados.

        Args:
            entrada_usuario: Texto del usuario (ej: "ingeniero de sistemas, plomería")
            max_servicios: Máximo número de servicios a extraer (default: SERVICIOS_MAXIMOS)

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
            logger.info(f"🔄 Transformando entrada a servicios: {entrada_usuario[:50]}...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": _crear_prompt_sistema(),
                    },
                    {
                        "role": "user",
                        "content": _crear_prompt_usuario(entrada_usuario, max_servicios),
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
                                    "description": "Lista de servicios específicos extraídos",
                                }
                            },
                            "required": ["servicios"],
                            "additionalProperties": False,
                        },
                    },
                },
                temperature=0.1,  # Baja temperatura para consistencia
                timeout=10.0,
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

            servicios = _normalizar_y_limitar_servicios(servicios, max_servicios)
            if not servicios:
                logger.warning("⚠️ Servicios inválidos tras normalización")
                return None

            logger.info(f"✅ Transformación exitosa: {len(servicios)} servicios extraídos")
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
    """
    Crea el prompt del sistema para optimizar transformación de servicios.

    Este prompt está diseñado para funcionar con CUALQUIER tipo de proveedor
    de servicios, no solo técnicos. Es agnóstico a la industria.

    Returns:
        Prompt del sistema optimizado
    """
    return """Eres un experto en convertir descripciones de servicios profesionales en Ecuador a una lista clara y buscable.

TU OBJETIVO:
Transformar títulos profesionales en SERVICIOS ESPECÍFICOS en español neutro.

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

REGLAS DE TRANSFORMACIÓN:

1. SERVICIOS ESPECÍFICOS, NO TÍTULOS:
   ❌ "Ingeniero de sistemas" → ✅ "desarrollo de software"
   ❌ "Arquitecto" → ✅ "diseño de planos arquitectónicos"
   ❌ "Abogado" → ✅ "asesoría legal"
   ❌ "Médico" → ✅ "consulta médica general"

2. USA ESPAÑOL NEUTRO, NUNCA INGLÉS:
   ❌ "community manager" → ✅ "gestión de redes sociales"
   ❌ "seo" → ✅ "posicionamiento web"
   ❌ "ads" → ✅ "publicidad digital"

3. ENFOQUE EN PROBLEMAS/NECESIDADES DE CLIENTES:
   Piensa: ¿Qué buscaría un cliente con un problema?
   - Cliente con "tubería rota" busca "reparación de fugas", no "plomero"
   - Cliente con "impuestos" busca "declaración de impuestos", no "contador"

4. NO INVENTES NI EXPANDAS ALCANCE:
   - No agregues atributos o detalles no mencionados.
   - No amplíes a sectores no indicados por el usuario.
   - Reescribe sin cambiar el sentido original.

5. RESPETA LA CANTIDAD DECLARADA:
   - No excedas la cantidad de servicios que el proveedor escribió.
   - Solo separa si el mismo ítem incluye dos servicios explícitos.

FORMATO DE SALIDA:
Devuelve SOLO una lista JSON de strings en español, sin explicaciones adicionales.

IMPORTANTE:
- No inventes servicios ni agregues calificativos.
- No excedas la cantidad declarada por el proveedor.
- Cada servicio debe ser entendible por un cliente sin conocimientos técnicos.
"""


def _crear_prompt_usuario(entrada: str, max_servicios: int) -> str:
    """
    Crea el prompt del usuario con la entrada a transformar.

    Args:
        entrada: Texto del usuario a transformar
        max_servicios: Máximo número de servicios a extraer

    Returns:
        Prompt del usuario
    """
    return f"""Transforma la siguiente entrada en servicios específicos y optimizados para búsqueda:

ENTRADA DEL USUARIO:
"{entrada}"

EXTRAE MÁXIMO {max_servicios} servicios específicos.

Recuerda:
- Sé específico, no uses títulos profesionales
- Piensa en qué buscaría un cliente con un problema
- Usa lenguaje sencillo que cualquiera entienda
- Separa servicios distintos que estén mencionados

Responde SOLO con el JSON de la lista de servicios."""


def _normalizar_y_limitar_servicios(servicios: List[str], max_servicios: int) -> List[str]:
    """
    Normaliza, deduplica y limita la lista final de servicios.

    Este paso es defensivo: incluso si el modelo excede el límite pedido,
    la salida se recorta a max_servicios.
    """
    resultado: List[str] = []

    for servicio in servicios:
        texto = str(servicio).strip()
        if not texto or texto in resultado:
            continue
        resultado.append(texto)
        if len(resultado) >= max_servicios:
            break

    return resultado


# Función auxiliar para usar directamente sin instanciar la clase
async def transformar_texto_a_servicios(
    entrada: str,
    cliente_openai: AsyncOpenAI,
    modelo: Optional[str] = None,
    max_servicios: int = SERVICIOS_MAXIMOS,
) -> Optional[List[str]]:
    """
    Función de conveniencia para transformar texto a servicios.

    Args:
        entrada: Texto del usuario
        cliente_openai: Cliente de OpenAI
        modelo: Modelo a usar (default: desde env o gpt-4o-mini)
        max_servicios: Máximo de servicios

    Returns:
        Lista de servicios o None
    """
    transformador = TransformadorServicios(cliente_openai, modelo)
    return await transformador.transformar_a_servicios(entrada, max_servicios)
