"""Servicio de validación de proveedores con IA."""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


class ValidadorProveedoresIA:
    """
    Servicio de validación de proveedores usando IA.

    Usa OpenAI para validar que los proveedores encontrados REALMENTE
    puedan ayudar con la necesidad del usuario.
    """

    def __init__(
        self,
        cliente_openai: AsyncOpenAI,
        semaforo_openai: asyncio.Semaphore,
        tiempo_espera_openai: float,
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de validación.

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

    async def validar_proveedores(
        self,
        necesidad_usuario: str,
        proveedores: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Usa IA para validar que los proveedores encontrados REALMENTE puedan ayudar
        con la necesidad del usuario.

        Analiza tanto la profesión como los servicios de cada proveedor para determinar
        si tiene la capacidad y experiencia apropiada.

        Args:
            necesidad_usuario: Necesidad del usuario (ej: "marketing", "community manager")
            proveedores: Lista de proveedores a validar

        Returns:
            Lista solo con los proveedores validados por la IA.
        """
        if not proveedores:
            return []

        if not self.cliente_openai:
            self.logger.warning("⚠️ validar_proveedores sin cliente OpenAI")
            return proveedores

        self.logger.info(
            f"🤖 Validando {len(proveedores)} proveedores con IA para '{necesidad_usuario}'"
        )

        # Construir prompt con información completa de proveedores
        proveedores_info = []
        for i, p in enumerate(proveedores):
            # Extraer información relevante del proveedor
            # Manejar tanto "profession" (singular) como "professions" (plural lista)
            profesion_cruda = p.get("profession") or p.get("professions")
            if isinstance(profesion_cruda, list):
                profesion = ", ".join(str(prof) for prof in profesion_cruda[:3])
            else:
                profesion = str(profesion_cruda) if profesion_cruda else "N/A"

            servicios = p.get("services", "N/A")
            lista_servicios = p.get("services_list", [])
            experiencia = p.get("experience_years") or p.get("years_of_experience", "N/A")
            calificacion = p.get("rating", "N/A")

            # Si services_list está disponible, usarlo, si no, usar services
            if lista_servicios and isinstance(lista_servicios, list):
                texto_servicios = ", ".join(str(s) for s in lista_servicios[:5])
            else:
                texto_servicios = str(servicios)

            texto_proveedor = f"""Proveedor {i+1}:
- Profesión: {profesion}
- Servicios: {texto_servicios}
- Experiencia: {experiencia} años
- Rating: {calificacion}"""
            proveedores_info.append(texto_proveedor)

        bloque_proveedores = "\n".join(proveedores_info)

        prompt_sistema = f"""Eres un experto en servicios profesionales. Tu tarea es analizar si cada proveedor PUEDE ayudar con esta necesidad del usuario.

IMPORTANTE: Los servicios pueden estar en español o inglés. Términos como "community manager", "social media manager", "community management" son EQUIVALENTES a "gestor de redes sociales", "manejo de redes sociales", "gestión de redes sociales".

NECESIDAD DEL USUARIO: "{necesidad_usuario}"

{bloque_proveedores}

Para CADA proveedor, responde si PUEDE ayudar o NO ayudar.

Criterios importantes:
1. La profesión del proveedor debe ser APROPIADA para la necesidad
   - Ejemplo: Para "contratación pública", un ABOGADO es apropiado, un MÉDICO NO lo es
   - Ejemplo: Para "marketing", un PUBLICISTA es apropiado, un PLOMERO NO lo es
   - Ejemplo: Para "gestor de redes sociales", "community manager" o "social media" son APROPIADOS

2. Los servicios que ofrece deben ser RELEVANTES y APLICABLES
   - No basta con mencionar palabras clave
   - Los servicios deben demostrar capacidad real de atender la necesidad
   - Acepta términos en inglés o español que sean equivalentes
   - "community manager" = "gestor de redes sociales" ✓
   - "social media" = "redes sociales" ✓
   - "marketing" = "mercadeo" ✓

3. La experiencia debe ser APLICABLE a la necesidad
   - No solo mencionar el término, sino tener experiencia real en ese servicio

Responde SOLO con JSON (array de booleanos, en el mismo orden):
[
  true,   // Proveedor 1: SÍ puede ayudar
  false,  // Proveedor 2: NO puede ayudar
  true,   // Proveedor 3: SÍ puede ayudar
  ...
]

NO incluyas explicaciones. Solo el array de booleanos."""

        self.logger.info(f"📋 Prompt enviado a IA de validación:\n{prompt_sistema[:1000]}...")

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Eres un experto analista de servicios profesionales. Analizas si un proveedor tiene la capacidad real de ayudar con una necesidad específica basándote en su profesión y servicios.",
                            },
                            {"role": "user", "content": prompt_sistema},
                        ],
                        temperature=0.3,
                        max_tokens=150,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                self.logger.warning("⚠️ OpenAI respondió sin choices en validar_proveedores")
                return proveedores

            contenido = (respuesta.choices[0].message.content or "").strip()
            if contenido.startswith("```"):
                contenido = re.sub(
                    r"^```(?:json)?", "", contenido, flags=re.IGNORECASE
                ).strip()
                contenido = re.sub(r"```$", "", contenido).strip()

            self.logger.debug(f"🤖 Respuesta validación IA: {contenido[:200]}")

            lista_validacion = json.loads(contenido)

            if not isinstance(lista_validacion, list):
                self.logger.warning(
                    f"⚠️ Respuesta de validación no es array: {type(lista_validacion)}"
                )
                return proveedores

            if len(lista_validacion) != len(proveedores):
                self.logger.warning(
                    f"⚠️ Respuesta IA tiene {len(lista_validacion)} valores, "
                    f"pero esperaba {len(proveedores)}"
                )
                # Ajustar longitud si es necesario
                lista_validacion = lista_validacion[: len(proveedores)]

            # Filtrar proveedores validados
            proveedores_validados = []
            for proveedor, es_valido in zip(proveedores, lista_validacion):
                if es_valido and isinstance(es_valido, bool) and es_valido:
                    proveedores_validados.append(proveedor)

            self.logger.info(
                f"✅ Validación IA: {len(proveedores_validados)}/{len(proveedores)} "
                f"proveedores validados para '{necesidad_usuario}'"
            )

            return proveedores_validados

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en validar_proveedores, retornando todos")
            return proveedores
        except json.JSONDecodeError as exc:
            self.logger.warning(f"⚠️ Error parseando JSON validación: {exc}")
            return proveedores
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en validación IA, retornando todos: {exc}")
            return proveedores
