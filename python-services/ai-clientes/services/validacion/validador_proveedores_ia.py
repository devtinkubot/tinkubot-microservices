"""Servicio de validación de proveedores con IA."""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from config.configuracion import configuracion


EJEMPLO_RESPUESTA_JSON_VALIDACION = """{
  "results": [
    {"can_help": true, "confidence": 0.91, "reason": "experiencia directa"},
    {"can_help": false, "confidence": 0.22, "reason": "servicio no aplicable"}
  ]
}"""


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

    @staticmethod
    def _extraer_json_parseable(contenido: str) -> Optional[Any]:
        texto = (contenido or "").strip()
        if not texto:
            return None

        if texto.startswith("```"):
            texto = re.sub(r"^```(?:json)?", "", texto, flags=re.IGNORECASE).strip()
            texto = re.sub(r"```$", "", texto).strip()

        candidatos = [texto]
        inicio_objeto = texto.find("{")
        fin_objeto = texto.rfind("}")
        if inicio_objeto != -1 and fin_objeto > inicio_objeto:
            candidatos.append(texto[inicio_objeto : fin_objeto + 1])
        inicio_lista = texto.find("[")
        fin_lista = texto.rfind("]")
        if inicio_lista != -1 and fin_lista > inicio_lista:
            candidatos.append(texto[inicio_lista : fin_lista + 1])

        for candidato in candidatos:
            try:
                return json.loads(candidato)
            except json.JSONDecodeError:
                continue
        return None

    def _normalizar_lista_validacion(
        self, payload: Any, total_proveedores: int
    ) -> Optional[List[Any]]:
        if isinstance(payload, dict):
            resultados = payload.get("results")
            if isinstance(resultados, list):
                payload = resultados

        if not isinstance(payload, list):
            return None

        if len(payload) != total_proveedores:
            self.logger.warning(
                "⚠️ Respuesta IA tiene %s valores, pero esperaba %s",
                len(payload),
                total_proveedores,
            )
        return payload[:total_proveedores]

    async def _solicitar_validacion(
        self,
        *,
        prompt_usuario: str,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        parametros: Dict[str, Any] = {
            "model": self.MODELO_VALIDACION,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un experto analista de servicios profesionales. "
                        "Responde solo JSON válido."
                    ),
                },
                {"role": "user", "content": prompt_usuario},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if response_format:
            parametros["response_format"] = response_format

        return await self.cliente_openai.chat.completions.create(**parametros)

    async def validar_proveedores(
        self,
        necesidad_usuario: str,
        descripcion_problema: Optional[str],
        proveedores: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Usa IA para validar que los proveedores encontrados REALMENTE puedan ayudar
        con la necesidad del usuario.

        Analiza tanto la profesión como los servicios de cada proveedor para determinar
        si tiene la capacidad y experiencia apropiada.

        Args:
            necesidad_usuario: Necesidad del usuario (ej: "marketing digital", "desarrollo web")
            descripcion_problema: Descripción completa del problema del cliente
            proveedores: Lista de proveedores a validar

        Returns:
            Lista de proveedores enriquecidos con decisión, confianza y razón.
        """
        if not proveedores:
            return []

        if not self.cliente_openai:
            self.logger.warning("⚠️ validar_proveedores sin cliente OpenAI")
            return []

        self.logger.info(
            f"🤖 Validando {len(proveedores)} proveedores con IA para '{necesidad_usuario}'"
        )
        problema = (descripcion_problema or necesidad_usuario or "").strip()

        # Construir prompt con información completa de proveedores
        proveedores_info = []
        for i, p in enumerate(proveedores):
            # Extraer información relevante del proveedor
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
- Servicios: {texto_servicios}
- Experiencia: {experiencia} años
- Rating: {calificacion}"""
            proveedores_info.append(texto_proveedor)

        bloque_proveedores = "\n".join(proveedores_info)

        prompt_sistema = f"""Eres un experto en servicios profesionales. Tu tarea es analizar si cada proveedor PUEDE ayudar con esta necesidad del usuario.

IMPORTANTE: Evalúa equivalencia semántica entre términos en distintos idiomas cuando representen el mismo servicio.

NECESIDAD DETECTADA: "{necesidad_usuario}"
PROBLEMA ESPECÍFICO DEL CLIENTE: "{problema}"

{bloque_proveedores}

Para CADA proveedor, responde si PUEDE ayudar o NO ayudar.

Criterios importantes:
1. Los servicios que ofrece deben ser RELEVANTES y APLICABLES
   - No basta con mencionar palabras clave
   - Los servicios deben demostrar capacidad real de atender la necesidad
   - "Desarrollo Software Backend" NO es automáticamente adecuado para "bugs de página web"
   - Un desarrollador backend probablemente NO puede ayudar con problemas frontend

2. Considera el contexto específico proporcionado
   - "Bug en página web" requiere conocimiento de HTML/CSS/JavaScript
   - "Error en base de datos" requiere conocimiento SQL/Base de datos
   - "App no funciona" requiere debugging de aplicaciones

Responde SOLO con JSON válido, usando exactamente este formato:
{EJEMPLO_RESPUESTA_JSON_VALIDACION}

NO incluyas markdown, fences ni explicaciones fuera del JSON."""

        self.logger.info(f"📋 Prompt enviado a IA de validación:\n{prompt_sistema[:1000]}...")

        try:
            async with self.semaforo_openai:
                self.logger.info(
                    "validator_request_started providers=%s model=%s format=%s",
                    len(proveedores),
                    self.MODELO_VALIDACION,
                    "json_object",
                )
                respuesta = await asyncio.wait_for(
                    self._solicitar_validacion(
                        prompt_usuario=prompt_sistema,
                        max_tokens=400,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                self.logger.warning("⚠️ OpenAI respondió sin choices en validar_proveedores")
                return []

            contenido = (respuesta.choices[0].message.content or "").strip()
            self.logger.debug(f"🤖 Respuesta validación IA: {contenido[:200]}")
            payload = self._extraer_json_parseable(contenido)
            lista_validacion = self._normalizar_lista_validacion(payload, len(proveedores))

            if lista_validacion is None:
                self.logger.warning("validator_parse_error stage=primary")
                prompt_reintento = (
                    f"Necesidad: {necesidad_usuario}\n"
                    f"Problema: {problema}\n"
                    f"Proveedores:\n{bloque_proveedores}\n\n"
                    "Devuelve SOLO un objeto JSON con la clave 'results'. "
                    "Cada item debe tener can_help, confidence y reason."
                )
                self.logger.info("validator_retry_used providers=%s", len(proveedores))
                respuesta = await asyncio.wait_for(
                    self._solicitar_validacion(
                        prompt_usuario=prompt_reintento,
                        max_tokens=300,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self.tiempo_espera_openai,
                )
                contenido = (respuesta.choices[0].message.content or "").strip()
                payload = self._extraer_json_parseable(contenido)
                lista_validacion = self._normalizar_lista_validacion(
                    payload, len(proveedores)
                )
                if lista_validacion is None:
                    self.logger.warning("validator_parse_error stage=retry")
                    return []

            proveedores_validados = []
            for proveedor, decision in zip(proveedores, lista_validacion):
                if isinstance(decision, bool):
                    can_help = decision
                    confidence = 1.0 if decision else 0.0
                    reason = "legacy_boolean_response"
                else:
                    can_help = bool((decision or {}).get("can_help"))
                    try:
                        confidence = max(
                            0.0,
                            min(1.0, float((decision or {}).get("confidence") or 0.0)),
                        )
                    except (TypeError, ValueError):
                        confidence = 0.0
                    reason = str((decision or {}).get("reason") or "").strip()
                if not can_help:
                    continue
                proveedor_enriquecido = dict(proveedor)
                proveedor_enriquecido["validation_confidence"] = confidence
                proveedor_enriquecido["validation_reason"] = reason or None
                proveedores_validados.append(proveedor_enriquecido)

            self.logger.info(
                f"✅ Validación IA: {len(proveedores_validados)}/{len(proveedores)} "
                f"proveedores validados para '{necesidad_usuario}'"
            )
            self.logger.info(
                "validator_final_pass_count passed=%s total=%s",
                len(proveedores_validados),
                len(proveedores),
            )

            return proveedores_validados

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en validar_proveedores, fail-closed")
            return []
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en validación IA, fail-closed: {exc}")
            return []
    MODELO_VALIDACION = (
        configuracion.modelo_validacion
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )
