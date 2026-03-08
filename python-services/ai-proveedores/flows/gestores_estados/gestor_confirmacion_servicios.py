"""Manejador del estado awaiting_services_confirmation."""

import logging
import re
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.utilidades import (
    es_servicio_critico_generico,
    mensaje_pedir_precision_servicio,
)
from templates.registro import (
    mensaje_confirmacion_servicios,
    mensaje_correccion_servicios,
)

logger = logging.getLogger(__name__)


def mostrar_confirmacion_servicios(
    flujo: Dict[str, Any], servicios_transformados: List[str]
) -> Dict[str, Any]:
    """
    Muestra la confirmación de los servicios transformados.

    Este método se llama cuando OpenAI ha transformado la entrada del usuario
    en servicios optimizados y necesitamos confirmación.

    Args:
        flujo: Diccionario del flujo conversacional
        servicios_transformados: Lista de servicios transformados por OpenAI

    Returns:
        Respuesta con mensaje de confirmación
    """
    logger.info(f"📋 Mostrando {len(servicios_transformados)} servicios para confirmación")

    # Guardar servicios temporalmente en el flujo
    flujo["servicios_temporales"] = servicios_transformados

    return {
        "success": True,
        "messages": [{"response": mensaje_confirmacion_servicios(servicios_transformados)}],
    }


async def manejar_confirmacion_servicios(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Procesa la respuesta del usuario a la confirmación de servicios.

    Args:
        flujo: Diccionario del flujo conversacional
        texto_mensaje: Respuesta del usuario ("1" para aceptar, "2" para corregir,
                      o nueva lista de servicios manual)

    Returns:
        Respuesta con éxito y siguiente paso, o error de validación
    """
    if not texto_mensaje:
        return {
            "success": True,
            "messages": [
                {
                    "response": "*Por favor selecciona una opción:*\n"
                    "*1.* Sí, continuar\n"
                    "*2.* No, corregir"
                }
            ],
        }

    texto_limpio = texto_mensaje.strip().lower()

    # Opción 1: Aceptar los servicios
    if texto_limpio == "1" or texto_limpio in {"si", "sí", "aceptar", "acepto", "ok"}:
        servicios_temporales = flujo.get("servicios_temporales", [])

        if not servicios_temporales:
            logger.error("❌ No hay servicios temporales para confirmar")
            return {
                "success": True,
                "messages": [
                    {"response": "*Error: No hay servicios para confirmar. Por favor escribe tus servicios nuevamente.*"}
                ],
            }

        # Guardar los servicios confirmados
        flujo["specialty"] = ", ".join(servicios_temporales)
        del flujo["servicios_temporales"]

        logger.info(f"✅ Servicios confirmados: {len(servicios_temporales)} servicios")

        # Cambiar al siguiente estado
        flujo["state"] = "awaiting_experience"

        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*¿Cuántos años de experiencia tienes?* "
                        "(escribe un número, ej: 5)"
                    )
                },
            ],
        }

    # Opción 2: Corregir manualmente
    if texto_limpio == "2" or texto_limpio in {"no", "corregir", "editar", "cambiar"}:
        return {
            "success": True,
            "messages": [{"response": mensaje_correccion_servicios()}],
        }

    # Si no es "1" o "2", asumimos que es una corrección manual
    return await procesar_correccion_manual(flujo, texto_mensaje, cliente_openai)


def _extraer_servicios_desde_texto(texto_mensaje: str) -> List[str]:
    servicios = []
    for item in re.split(r"[;,/\n]+", texto_mensaje.strip()):
        item = item.strip()
        if item and len(item) >= 2:
            servicios.append(item)
    return servicios


async def _normalizar_o_conservar_servicios(
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    max_servicios: int = 10,
) -> List[str]:
    servicios_parseados = _extraer_servicios_desde_texto(texto_mensaje)
    if not servicios_parseados:
        return []

    if not cliente_openai:
        return servicios_parseados[:max_servicios]

    try:
        from infrastructure.openai.transformador_servicios import TransformadorServicios

        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            texto_mensaje,
            max_servicios=max_servicios,
        )
        if servicios_transformados:
            return servicios_transformados[:max_servicios]
    except Exception as exc:
        logger.warning("⚠️ Error re-normalizando corrección manual: %s", exc)

    return servicios_parseados[:max_servicios]


async def procesar_correccion_manual(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Procesa la corrección manual de servicios por parte del usuario.

    Args:
        flujo: Diccionario del flujo conversacional
        texto_mensaje: Nueva lista de servicios del usuario

    Returns:
        Respuesta confirmando la corrección y continuando
    """
    # Limpiar y procesar la entrada manual
    texto_limpio = texto_mensaje.strip()

    if len(texto_limpio) < 2:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Los servicios son muy cortos.* "
                        "Por favor escribe al menos 2 servicios separados por comas."
                    )
                }
            ],
        }

    servicios = _extraer_servicios_desde_texto(texto_limpio)

    if len(servicios) > 10:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Máximo 10 servicios permitidos.* "
                        f"Envíalos nuevamente (actualmente {len(servicios)})."
                    )
                }
            ],
        }

    servicios_normalizados = await _normalizar_o_conservar_servicios(
        texto_limpio,
        cliente_openai,
        max_servicios=10,
    )
    if not servicios_normalizados:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*No pude interpretar tus servicios.* "
                        "Por favor reescríbelos de forma más simple, separados por comas."
                    )
                }
            ],
        }

    servicio_generico = next(
        (
            servicio
            for servicio in servicios_normalizados
            if es_servicio_critico_generico(servicio)
        ),
        None,
    )
    if servicio_generico:
        return {
            "success": True,
            "messages": [
                {"response": mensaje_pedir_precision_servicio(servicio_generico)}
            ],
        }

    flujo["servicios_temporales"] = servicios_normalizados
    flujo["state"] = "awaiting_services_confirmation"

    logger.info(
        "✅ Servicios corregidos manualmente y re-normalizados: %s servicios",
        len(servicios_normalizados),
    )

    return {
        "success": True,
        "messages": [
            {"response": mensaje_confirmacion_servicios(servicios_normalizados)}
        ],
    }
