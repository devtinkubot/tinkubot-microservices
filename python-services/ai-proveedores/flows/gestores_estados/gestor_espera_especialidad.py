"""Manejador del estado awaiting_specialty."""

import logging
from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios

logger = logging.getLogger(__name__)


async def manejar_espera_especialidad(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Procesa la entrada del usuario para el campo especialidad/servicios.

    Fase 7: Ahora usa OpenAI para transformar títulos profesionales en
    servicios optimizados para búsquedas semánticas.

    Args:
        flujo: Diccionario del flujo conversacional
        texto_mensaje: Mensaje del usuario con los servicios
        cliente_openai: Cliente de OpenAI (opcional, si no hay se salta transformación)

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación
    """
    especialidad_texto = limpiar_espacios(texto_mensaje)
    texto_minusculas = especialidad_texto.lower()
    logger.info(
        "🧩 servicios.ingreso raw='%s' openai=%s",
        especialidad_texto[:120],
        bool(cliente_openai),
    )

    if texto_minusculas in {"omitir", "ninguna", "na", "n/a"}:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Los servicios son obligatorios. Por favor escríbelos tal como los trabajas, separando con comas si hay varios.*"
                    )
                }
            ],
        }

    if len(especialidad_texto) < 2:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Los servicios deben tener al menos 2 caracteres. "
                        "Incluye tus servicios separados por comas (ej: gasfitería, mantenimiento).*"
                    )
                }
            ],
        }

    if len(especialidad_texto) > 300:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*El listado de servicios es muy largo (máx. 300 caracteres).* "
                        "Envía una versión resumida con tus principales servicios separados por comas."
                    )
                }
            ],
        }

    if not cliente_openai:
        logger.error("❌ OpenAI no configurado; no se puede normalizar servicios")
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*No pude procesar tus servicios en este momento.* "
                        "Por favor intenta nuevamente en unos minutos."
                    )
                }
            ],
        }

    try:
        from infrastructure.openai.transformador_servicios import (
            TransformadorServicios,
        )

        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            especialidad_texto, max_servicios=10
        )

        if not servicios_transformados:
            logger.warning("⚠️ Transformación OpenAI sin resultados")
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

        logger.info(
            "✅ servicios.transformados count=%s",
            len(servicios_transformados),
        )
        # Guardar servicios temporalmente para confirmación
        flujo["servicios_temporales"] = servicios_transformados
        flujo["state"] = "awaiting_services_confirmation"

        # Importar aquí para evitar circular dependency
        from flows.gestores_estados.gestor_confirmacion_servicios import (
            mostrar_confirmacion_servicios,
        )

        return mostrar_confirmacion_servicios(flujo, servicios_transformados)

    except Exception as e:
        logger.error("❌ Error en transformación OpenAI: %s", e)
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Tuvimos un problema al normalizar tus servicios.* "
                        "Por favor intenta nuevamente."
                    )
                }
            ],
        }
