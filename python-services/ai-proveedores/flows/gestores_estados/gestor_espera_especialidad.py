"""Manejador del estado awaiting_specialty."""

import re
from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


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

    # Fase 7: Si hay cliente OpenAI, transformar los servicios
    if cliente_openai:
        try:
            from infrastructure.openai.transformador_servicios import (
                TransformadorServicios,
            )

            transformador = TransformadorServicios(cliente_openai)
            servicios_transformados = await transformador.transformar_a_servicios(
                especialidad_texto, max_servicios=10
            )

            if servicios_transformados:
                # Guardar servicios temporalmente para confirmación
                flujo["servicios_temporales"] = servicios_transformados
                flujo["state"] = "awaiting_services_confirmation"

                # Importar aquí para evitar circular dependency
                from flows.gestores_estados.gestor_confirmacion_servicios import (
                    mostrar_confirmacion_servicios,
                )

                return mostrar_confirmacion_servicios(flujo, servicios_transformados)
            else:
                # Si falló la transformación, guardar tal cual came del usuario
                import logging
                logging.getLogger(__name__).warning(
                    "⚠️ Falló transformación de OpenAI, usando entrada original"
                )

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Error en transformación: {e}")

    # Fallback: Procesar manualmente sin OpenAI (comportamiento original)
    lista_servicios = [
        item.strip()
        for item in re.split(r"[;,/\n]+", especialidad_texto)
        if item and item.strip()
    ]

    if len(lista_servicios) > 10:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Incluye máximo 10 servicios.* Envía nuevamente tus principales servicios separados por comas."
                    )
                }
            ],
        }

    if any(len(servicio) > 120 for servicio in lista_servicios):
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*Cada servicio debe ser breve (máx. 120 caracteres).* "
                        "Recorta descripciones muy largas y envía de nuevo la lista."
                    )
                }
            ],
        }

    flujo["specialty"] = (
        ", ".join(lista_servicios) if lista_servicios else especialidad_texto
    )
    flujo["state"] = "awaiting_experience"
    return {
        "success": True,
        "messages": [{"response": ("*¿Cuántos años de experiencia tienes?* (escribe un número)")}],
    }
