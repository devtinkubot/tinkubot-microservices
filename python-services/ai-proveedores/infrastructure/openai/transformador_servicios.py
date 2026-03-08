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

from openai import AsyncOpenAI

from config.configuracion import configuracion
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS

logger = logging.getLogger(__name__)

_VERBOS_SENSIBLES = {
    "configuracion": {"instalacion", "instalar"},
    "configurar": {"instalacion", "instalar"},
    "reparacion": {"instalacion", "instalar", "mantenimiento"},
    "reparar": {"instalacion", "instalar", "mantenimiento"},
    "desarrollo": {"instalacion", "instalar", "soporte"},
    "desarrollar": {"instalacion", "instalar", "soporte"},
}

_CONECTORES_DIVISION = re.compile(r"\s*(?:,|;|/|\n)\s*")


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

            servicios = _normalizar_y_limitar_servicios(
                servicios,
                max_servicios,
                entrada_usuario=entrada_usuario,
            )
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
    return """Eres un experto en convertir lo que escribe un proveedor en servicios claros, específicos y buscables en Ecuador.

TU OBJETIVO:
Transformar profesiones, especialidades o descripciones libres en SERVICIOS CONCRETOS que un cliente realmente buscaría.

PRIORIDAD SEMÁNTICA:
- Si el proveedor dio detalle suficiente, conserva ese detalle.
- Prefiere subservicios concretos sobre categorías paraguas.
- Solo usa una categoría general cuando el texto sea ambiguo y no dé más contexto.

REGLAS DE TRANSFORMACIÓN:

1. DEVUELVE SERVICIOS, NO OFICIOS NI TÍTULOS:
   - "abogado" → "asesoría legal"
   - "plomero" → "reparación de fugas", "destape de cañerías"
   - "carpintero" → "fabricación de muebles a medida", "reparación de muebles de madera"
   - "ingeniero de sistemas" → "desarrollo de software"

2. SI HAY DETALLE, NO LO GENERALICES:
   - "abogado para rebaja de pensión alimenticia" → "asesoría para rebaja de pensión alimenticia"
   - "abogado en contratación pública" → "asesoría en contratación pública"
   - "plomero para destapar lavamanos" → "destape de cañerías en lavamanos"
   - "carpintero para arreglar muebles" → "restauración de muebles"
   - "contador para declaración de renta" → "declaración de impuestos"

3. USA LENGUAJE DE BÚSQUEDA DEL CLIENTE:
   Piensa en cómo buscaría el servicio una persona común.
   - mejor "reparación de fugas" que "plomería"
   - mejor "asesoría para pensión alimenticia" que "abogado"
   - mejor "gestión de redes sociales" que "community manager"

4. ESPAÑOL NEUTRO, SIN INGLÉS:
   - "community manager" → "gestión de redes sociales"
   - "seo" → "posicionamiento web"
   - "ads" → "publicidad digital"

5. NO INVENTES NI EXPANDAS ALCANCE:
   - No agregues especialidades que el proveedor no insinuó.
   - No conviertas un servicio puntual en una lista amplia sin base.
   - Si el texto es genérico, propone solo servicios típicos y buscables de esa ocupación.
   - No cambies el verbo principal si el proveedor ya fue específico.
     Ejemplo: "configuración" no se convierte en "instalación".
   - No conviertas "desarrollo de software" en formas telegráficas como "desarrollo software".

6. RESPETA LA CANTIDAD DECLARADA:
   - No excedas la cantidad de servicios que el proveedor escribió.
   - Solo separa cuando el mismo texto incluya servicios distintos de forma explícita.
   - Si el proveedor escribió una sola ocupación, puedes devolver entre 1 y 3 servicios típicos como máximo.
   - Si una frase describe un solo bloque de servicio, mantenla como un solo servicio.

FORMATO DE SALIDA:
Devuelve SOLO una lista JSON de strings en español, sin explicaciones adicionales.

IMPORTANTE:
- Cada servicio debe ser corto, claro y entendible por un cliente sin conocimientos técnicos.
- Evita categorías demasiado amplias si el texto permite algo más específico.
- Conserva términos de dominio relevantes cuando el proveedor ya los mencionó.
- Prefiere conservar frases ya buscables casi textuales antes que reescribirlas de forma más agresiva.
- "configuración de redes e internet" puede mantenerse igual o separarse en "configuración de redes" y "configuración de internet".
- "configuración de redes e internet" NO debe convertirse en "instalación de internet".
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
- No devuelvas profesiones ni oficios como salida final
- Conserva el detalle cuando el proveedor ya lo escribió
- Piensa en qué buscaría un cliente con un problema real
- Usa lenguaje sencillo que cualquiera entienda
- Solo separa servicios distintos que estén claramente mencionados
- No cambies el verbo principal de la acción si ya es claro en la entrada

Responde SOLO con el JSON de la lista de servicios."""


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
    limite_razonable = min(max_servicios, _cantidad_servicios_declarados(entrada_usuario))
    return len(servicios) > limite_razonable


def _tiene_cambio_verbo_sensible(entrada_usuario: str, servicio: str) -> bool:
    entrada_tokens = _tokenizar_texto(entrada_usuario)
    servicio_tokens = _tokenizar_texto(servicio)
    for verbo_entrada, verbos_prohibidos in _VERBOS_SENSIBLES.items():
        if verbo_entrada in entrada_tokens and servicio_tokens.intersection(verbos_prohibidos):
            return True
    return False


def _ajustar_frase_natural(servicio: str) -> str:
    texto = " ".join((servicio or "").strip().split())
    reemplazos = {
        "desarrollo software": "desarrollo de software",
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

    servicios_postprocesados = [_ajustar_frase_natural(str(servicio)) for servicio in servicios]
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
                "↩️ Rechazando servicio por cambio semántico sensible: entrada='%s' servicio='%s'",
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
