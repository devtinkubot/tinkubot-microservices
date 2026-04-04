"""Servicio de validación de proveedores con IA."""

import asyncio
import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from config.configuracion import configuracion
from openai import AsyncOpenAI

EJEMPLO_RESPUESTA_JSON_VALIDACION = """{
  "results": [
    {"can_help": true, "confidence": 0.91, "reason": "experiencia directa"},
    {"can_help": false, "confidence": 0.22, "reason": "servicio no aplicable"}
  ]
}"""

_DOMINIO_FAMILIA_ALIASES = {
    "automotriz": "vehiculos",
    "vehiculos": "vehiculos",
    "transporte": "movilidad",
    "movilidad": "movilidad",
    "construccion_hogar": "construccion_hogar",
    "mantenimiento": "mantenimiento",
    "tecnologia": "tecnologia",
    "legal": "legal",
    "salud": "salud",
    "marketing": "marketing",
    "financiero": "financiero",
    "academico": "academico",
    "gastronomia_alimentos": "gastronomia_alimentos",
    "cuidados_asistencia": "cuidados_asistencia",
    "eventos": "eventos",
    "inmobiliario": "inmobiliario",
    "servicios_administrativos": "servicios_administrativos",
    "belleza": "belleza",
    "otros": "otros",
    "general": "general",
}

_DOMINIOS_GENERICOS = {"otros", "general", "servicios_administrativos"}
_CATEGORIAS_GENERICAS = {
    "mantenimiento",
    "general",
    "otros",
    "servicios",
    "servicios varios",
}


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
        validacion_proveedores_ia_only: Optional[bool] = None,
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
        self.validacion_proveedores_ia_only = (
            configuracion.validacion_proveedores_ia_only
            if validacion_proveedores_ia_only is None
            else bool(validacion_proveedores_ia_only)
        )

    @staticmethod
    def _normalizar_texto(texto: Optional[str]) -> str:
        if not texto:
            return ""
        base = unicodedata.normalize("NFD", str(texto).lower().strip())
        sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
        return re.sub(r"\s+", " ", limpio).strip()

    @classmethod
    def _tokens(cls, texto: Optional[str]) -> set[str]:
        return {
            token for token in cls._normalizar_texto(texto).split() if len(token) >= 3
        }

    @staticmethod
    def _normalizar_codigo_dominio(texto: Optional[str]) -> str:
        return ValidadorProveedoresIA._normalizar_texto(texto).replace(" ", "_")

    @staticmethod
    def _familia_dominio(texto: Optional[str]) -> str:
        codigo = ValidadorProveedoresIA._normalizar_codigo_dominio(texto)
        if not codigo:
            return ""
        return _DOMINIO_FAMILIA_ALIASES.get(codigo, codigo)

    @classmethod
    def _overlap(cls, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @classmethod
    def _evaluar_coherencia_taxonomica(
        cls,
        *,
        request_domain_code: Optional[str],
        request_category_name: Optional[str],
        request_service_text: str,
        provider_domain_code: Optional[str],
        provider_category_name: Optional[str],
        provider_service_text: str,
    ) -> Dict[str, Any]:
        request_domain = cls._normalizar_codigo_dominio(request_domain_code)
        provider_domain = cls._normalizar_codigo_dominio(provider_domain_code)
        request_family = cls._familia_dominio(request_domain)
        provider_family = cls._familia_dominio(provider_domain)

        domain_coherence = False
        if request_family and provider_family:
            domain_coherence = request_family == provider_family
        elif not request_domain or not provider_domain:
            domain_coherence = True
        elif (
            request_domain in _DOMINIOS_GENERICOS
            or provider_domain in _DOMINIOS_GENERICOS
        ):
            domain_coherence = True

        request_category_tokens = cls._tokens(request_category_name)
        provider_category_tokens = cls._tokens(provider_category_name)
        category_overlap = cls._overlap(
            request_category_tokens, provider_category_tokens
        )
        category_coherence = category_overlap >= 0.18
        if not request_category_tokens or not provider_category_tokens:
            category_coherence = domain_coherence
        if (
            request_category_tokens & _CATEGORIAS_GENERICAS
            or provider_category_tokens & _CATEGORIAS_GENERICAS
        ):
            category_coherence = category_coherence or domain_coherence

        request_service_tokens = cls._tokens(request_service_text)
        provider_service_tokens = cls._tokens(provider_service_text)
        service_overlap = cls._overlap(request_service_tokens, provider_service_tokens)
        service_coherence = service_overlap >= 0.12 or domain_coherence

        score = (
            (1.0 if domain_coherence else 0.0) * 0.55
            + category_overlap * 0.30
            + service_overlap * 0.15
        )
        if request_domain and provider_domain and not domain_coherence:
            score = min(score, 0.35)

        final_decision = domain_coherence and (category_coherence or service_coherence)
        if score >= 0.65 and domain_coherence:
            final_decision = True

        return {
            "domain_coherence": domain_coherence,
            "category_coherence": category_coherence,
            "service_coherence": service_coherence,
            "taxonomy_coherence_score": max(0.0, min(1.0, score)),
            "taxonomy_family_request": request_family or None,
            "taxonomy_family_provider": provider_family or None,
            "taxonomy_final_decision": final_decision,
        }

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

    def _enriquecer_proveedor_timeout_fallback(
        self,
        *,
        proveedor: Dict[str, Any],
        necesidad_usuario: str,
        descripcion_problema: Optional[str],
        request_domain_code: Optional[str],
        request_category_name: Optional[str],
        request_domain: Optional[str],
        request_category: Optional[str],
    ) -> Dict[str, Any]:
        service_summary = str(
            proveedor.get("matched_service_summary")
            or proveedor.get("service_summary")
            or ""
        ).strip()
        service_list = " ".join(
            str(service).strip() for service in (proveedor.get("services") or [])
        )
        provider_service_parts = [
            str(proveedor.get("matched_service_name") or "").strip(),
            service_summary,
            service_list,
        ]
        provider_service_text = " ".join(part for part in provider_service_parts if part)
        coherencia = self._evaluar_coherencia_taxonomica(
            request_domain_code=request_domain_code,
            request_category_name=request_category_name,
            request_service_text=" ".join(
                part for part in [necesidad_usuario, descripcion_problema or ""] if part
            ),
            provider_domain_code=proveedor.get("domain_code"),
            provider_category_name=proveedor.get("category_name"),
            provider_service_text=provider_service_text,
        )
        proveedor_enriquecido = dict(proveedor)
        proveedor_enriquecido["validation_mode"] = "timeout_fallback"
        proveedor_enriquecido["validation_timeout"] = True
        proveedor_enriquecido["validation_confidence"] = coherencia[
            "taxonomy_coherence_score"
        ]
        proveedor_enriquecido["validation_reason"] = "validation_timeout_fallback"
        proveedor_enriquecido["taxonomy_coherence_score"] = coherencia[
            "taxonomy_coherence_score"
        ]
        proveedor_enriquecido["domain_coherence"] = coherencia["domain_coherence"]
        proveedor_enriquecido["category_coherence"] = coherencia["category_coherence"]
        proveedor_enriquecido["service_coherence"] = coherencia["service_coherence"]
        proveedor_enriquecido["taxonomy_family_request"] = coherencia[
            "taxonomy_family_request"
        ]
        proveedor_enriquecido["taxonomy_family_provider"] = coherencia[
            "taxonomy_family_provider"
        ]
        proveedor_enriquecido["taxonomy_final_decision"] = coherencia[
            "taxonomy_final_decision"
        ]
        proveedor_enriquecido["validation_raw"] = {
            "mode": "timeout_fallback",
            "domain_coherence": coherencia["domain_coherence"],
            "category_coherence": coherencia["category_coherence"],
            "service_coherence": coherencia["service_coherence"],
            "taxonomy_coherence_score": coherencia["taxonomy_coherence_score"],
            "taxonomy_final_decision": coherencia["taxonomy_final_decision"],
        }
        return proveedor_enriquecido

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

    async def validar_proveedores(  # noqa: C901
        self,
        necesidad_usuario: str,
        descripcion_problema: Optional[str],
        proveedores: List[Dict[str, Any]],
        request_domain_code: Optional[str] = None,
        request_category_name: Optional[str] = None,
        request_domain: Optional[str] = None,
        request_category: Optional[str] = None,
        search_profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Usa IA para validar que los proveedores encontrados REALMENTE puedan ayudar
        con la necesidad del usuario.

        Analiza tanto la profesión como los servicios de cada proveedor para determinar
        si tiene la capacidad y experiencia apropiada.

        Args:
            necesidad_usuario: Necesidad del usuario (ej: "marketing digital",
                "desarrollo web")
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
            "🤖 Validando %s proveedores con IA para '%s'",
            len(proveedores),
            necesidad_usuario,
        )
        problema = (descripcion_problema or necesidad_usuario or "").strip()
        dominio_request = request_domain_code or request_domain
        categoria_request = request_category_name or request_category
        perfil_busqueda = search_profile if isinstance(search_profile, dict) else {}
        primary_service_request = str(
            perfil_busqueda.get("primary_service") or necesidad_usuario or ""
        ).strip()
        signals_request = perfil_busqueda.get("signals") or []
        if isinstance(signals_request, str):
            signals_request = [signals_request]
        signals_request_text = ", ".join(
            str(signal).strip() for signal in signals_request if str(signal).strip()
        )

        # Construir prompt con información completa de proveedores
        proveedores_info = []
        for i, p in enumerate(proveedores):
            # Extraer información relevante del proveedor
            servicios = p.get("services", "N/A")
            lista_servicios = p.get("services_list", [])
            experiencia = p.get("experience_range") or p.get(
                "years_of_experience", "N/A"
            )
            calificacion = p.get("rating", "N/A")
            dominio_proveedor = p.get("domain_code") or "N/A"
            categoria_proveedor = p.get("category_name") or "N/A"
            servicio_matcheado = p.get("matched_service_name") or p.get(
                "service_name", "N/A"
            )
            resumen_servicio = p.get("matched_service_summary") or p.get(
                "service_summary",
                "N/A",
            )

            # Si services_list está disponible, usarlo, si no, usar services
            if lista_servicios and isinstance(lista_servicios, list):
                texto_servicios = ", ".join(str(s) for s in lista_servicios[:5])
            else:
                texto_servicios = str(servicios)

            texto_proveedor = f"""Proveedor {i+1}:
- Dominio: {dominio_proveedor}
- Categoria: {categoria_proveedor}
- Servicio matcheado: {servicio_matcheado}
- Resumen del servicio: {resumen_servicio}
- Servicios: {texto_servicios}
- Experiencia: {experiencia}
- Rating: {calificacion}"""
            proveedores_info.append(texto_proveedor)

        bloque_proveedores = "\n".join(proveedores_info)

        prompt_sistema = (
            "Eres un evaluador experto de proveedores para un marketplace de "
            "servicios en Ecuador.\n\n"
            "Tu tarea es decidir si cada proveedor puede ayudar realmente con "
            "la necesidad del cliente.\n\n"
            "PRINCIPIOS CLAVE\n"
            "- Evalúa capacidad real, no coincidencia literal de palabras.\n"
            "- Un proveedor puede ayudar aunque el nombre exacto del servicio "
            "no sea idéntico.\n"
            "- Debes considerar en conjunto:\n"
            "  1. servicio ofrecido\n"
            "  2. dominio de negocio\n"
            "  3. categoría\n"
            "- Si el servicio del proveedor resuelve la necesidad real del "
            "cliente, aprueba.\n"
            "- Si solo hay coincidencia superficial de palabras pero no "
            "capacidad real, rechaza.\n\n"
            "REGLA GENERAL\n"
            "Piensa así:\n"
            "1. ¿El proveedor ofrece un servicio que realmente resuelve la "
            "necesidad?\n"
            "2. ¿Ese servicio pertenece al mismo dominio funcional?\n"
            "3. ¿La categoría acompaña esa lectura?\n"
            "4. Si la respuesta es sí en lo funcional, responde can_help=true.\n\n"
            "IMPORTANTE\n"
            "- No bloquees por diferencias de etiqueta si el servicio es "
            "funcionalmente equivalente.\n"
            "- No dependas de nombres exactos.\n"
            "- No rechaces un proveedor solo porque la categoría use otra "
            "taxonomía cercana.\n"
            "- Sí rechaza cuando el proveedor no tiene capacidad real para "
            "resolver el problema del cliente.\n"
            "- Usa el contexto completo, no solo una palabra suelta.\n\n"
            "PERFIL CANONICO DE BUSQUEDA\n"
            f'- Servicio principal: "{primary_service_request or "N/A"}"\n'
            f'- Dominio canónico: "{perfil_busqueda.get("domain") or dominio_request or "N/A"}"\n'
            f'- Categoria canónica: "{perfil_busqueda.get("category") or categoria_request or "N/A"}"\n'
            f'- Senales auxiliares: "{signals_request_text or "N/A"}"\n\n'
            "EJEMPLOS DE EQUIVALENCIA FUNCIONAL\n"
            '- "arreglo de cejas" puede equivaler a:\n'
            "  - microblading de cejas\n"
            "  - micropigmentación de cejas\n"
            "  - diseño de cejas\n"
            "  - depilación y diseño de cejas\n"
            '- "estuco roto" puede equivaler a:\n'
            "  - reparación de estucos\n"
            "  - empastado y acabado de paredes\n"
            "  - pintura de empaste\n"
            '- "delivery de comida" puede equivaler a:\n'
            "  - transporte de alimentos\n"
            "  - servicio de entrega a domicilio\n"
            "  - mensajería con entrega de comida\n"
            "  - motorizado para delivery de comida\n"
            "  - repartidor de comida\n"
            "  - domiciliario\n"
            "  - delivery de alimentos\n"
            '- "corte de cabello" puede equivaler a:\n'
            "  - servicios de belleza y estética\n"
            "  - peluquería\n"
            "  - tratamientos capilares\n"
            '- "lavaplatos tapado" puede equivaler a:\n'
            "  - destape de tuberías\n"
            "  - plomería doméstica\n"
            '- "cerradura dañada" puede equivaler a:\n'
            "  - cerrajería\n"
            "  - apertura de puertas\n"
            "  - cambio de cerraduras\n\n"
            "CUANDO RECHAZAR\n"
            "- Si el servicio no resuelve el problema real.\n"
            "- Si el proveedor está en una familia funcional distinta y no hay "
            "equivalencia real.\n"
            "- Si solo hay cercanía temática, pero no capacidad práctica.\n"
            "- Si el match parece forzado.\n\n"
            "CUANDO APROBAR\n"
            "- Si el proveedor ofrece un servicio que realmente puede atender "
            "la necesidad.\n"
            "- Si el servicio es una variante, sinónimo o subservicio válido.\n"
            "- Si la categoría y el dominio apoyan esa lectura aunque no sean "
            "idénticos.\n\n"
            f'NECESIDAD DETECTADA: "{necesidad_usuario}"\n'
            f'PROBLEMA ESPECÍFICO DEL CLIENTE: "{problema}"\n'
            f'DOMINIO REQUERIDO: "{dominio_request or "N/A"}"\n'
            f'CATEGORIA REQUERIDA: "{categoria_request or "N/A"}"\n\n'
            f"{bloque_proveedores}\n\n"
            "Responde SOLO con JSON válido y nada más.\n\n"
            "Usa exactamente este formato:\n"
            "{\n"
            '  "results": [\n'
            "    {\n"
            '      "can_help": true,\n'
            '      "confidence": 0.91,\n'
            '      "reason": "explicación breve y concreta",\n'
            '      "matched_service_name": "nombre del servicio que mejor '
            'explica el match",\n'
            '      "domain_fit": true,\n'
            '      "category_fit": true,\n'
            '      "service_fit": true\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "REGLAS DE SALIDA\n"
            "- Devuelve un item por cada proveedor recibido.\n"
            "- Mantén el mismo orden de entrada.\n"
            "- confidence debe ser un número entre 0 y 1.\n"
            "- reason debe explicar por qué sí o no, sin rodeos.\n"
            "- matched_service_name debe ser el servicio concreto que te hizo "
            "decidir.\n"
            "- domain_fit, category_fit y service_fit deben reflejar tu "
            "evaluación semántica.\n"
            "- No incluyas markdown, texto extra ni fences."
        )

        self.logger.info(
            f"📋 Prompt enviado a IA de validación:\n{prompt_sistema[:1000]}..."
        )

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
                self.logger.warning(
                    "⚠️ OpenAI respondió sin choices en validar_proveedores"
                )
                return []

            contenido = (respuesta.choices[0].message.content or "").strip()
            self.logger.debug(f"🤖 Respuesta validación IA: {contenido[:200]}")
            payload = self._extraer_json_parseable(contenido)
            lista_validacion = self._normalizar_lista_validacion(
                payload, len(proveedores)
            )

            if lista_validacion is None:
                self.logger.warning("validator_parse_error stage=primary")
                prompt_reintento = (
                    f"Necesidad: {necesidad_usuario}\n"
                    f"Problema: {problema}\n"
                    f"Dominio requerido: {dominio_request or 'N/A'}\n"
                    f"Categoria requerida: {categoria_request or 'N/A'}\n"
                    f"Servicio principal: {primary_service_request or 'N/A'}\n"
                    f"Senales auxiliares: {signals_request_text or 'N/A'}\n"
                    f"Proveedores:\n{bloque_proveedores}\n\n"
                    "Devuelve SOLO un objeto JSON con la clave 'results'. "
                    "Cada item debe tener can_help, confidence, reason, "
                    "domain_coherence, category_coherence, service_coherence "
                    "y taxonomy_coherence_score."
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
                    self.logger.warning(
                        "validator_fallback_individual providers=%s",
                        len(proveedores),
                    )
                    proveedores_validados = []
                    for indice, proveedor in enumerate(proveedores):
                        prompt_individual = prompt_sistema.replace(
                            bloque_proveedores,
                            proveedores_info[indice],
                        )
                        respuesta_individual = await asyncio.wait_for(
                            self._solicitar_validacion(
                                prompt_usuario=prompt_individual,
                                max_tokens=220,
                                response_format={"type": "json_object"},
                            ),
                            timeout=self.tiempo_espera_openai,
                        )
                        if not respuesta_individual.choices:
                            continue

                        contenido_individual = (
                            respuesta_individual.choices[0].message.content or ""
                        ).strip()
                        payload_individual = self._extraer_json_parseable(
                            contenido_individual
                        )
                        lista_individual = self._normalizar_lista_validacion(
                            payload_individual, 1
                        )
                        if not lista_individual:
                            continue

                        decision = lista_individual[0]
                        if isinstance(decision, bool):
                            can_help = decision
                            confidence = 1.0 if decision else 0.0
                            reason = "legacy_boolean_response"
                            decision_data = {}
                        else:
                            can_help = bool((decision or {}).get("can_help"))
                            try:
                                confidence = max(
                                    0.0,
                                    min(
                                        1.0,
                                        float(
                                            (decision or {}).get("confidence") or 0.0
                                        ),
                                    ),
                                )
                            except (TypeError, ValueError):
                                confidence = 0.0
                            reason = str((decision or {}).get("reason") or "").strip()
                            decision_data = dict(decision or {})

                        service_summary = str(
                            proveedor.get("matched_service_summary")
                            or proveedor.get("service_summary")
                            or ""
                        ).strip()
                        service_list = " ".join(
                            str(service).strip()
                            for service in (proveedor.get("services") or [])
                        )
                        provider_service_parts = [
                            str(proveedor.get("matched_service_name") or "").strip(),
                            service_summary,
                            service_list,
                        ]
                        provider_service_text = " ".join(
                            part for part in provider_service_parts if part
                        )
                        if self.validacion_proveedores_ia_only:
                            coherencia = {
                                "domain_coherence": decision_data.get(
                                    "domain_coherence"
                                ),
                                "category_coherence": decision_data.get(
                                    "category_coherence"
                                ),
                                "service_coherence": decision_data.get(
                                    "service_coherence"
                                ),
                                "taxonomy_coherence_score": max(
                                    0.0,
                                    min(
                                        1.0,
                                        float(
                                            decision_data.get(
                                                "taxonomy_coherence_score"
                                            )
                                            or confidence
                                        ),
                                    ),
                                ),
                                "taxonomy_family_request": None,
                                "taxonomy_family_provider": None,
                                "taxonomy_final_decision": bool(can_help),
                            }
                        else:
                            coherencia = self._evaluar_coherencia_taxonomica(
                                request_domain_code=dominio_request,
                                request_category_name=categoria_request,
                                request_service_text=" ".join(
                                    part
                                    for part in [
                                        necesidad_usuario,
                                        problema,
                                    ]
                                    if part
                                ),
                                provider_domain_code=proveedor.get("domain_code"),
                                provider_category_name=proveedor.get("category_name"),
                                provider_service_text=provider_service_text,
                            )

                            if not coherencia["taxonomy_final_decision"]:
                                can_help = False
                                confidence = min(
                                    confidence, coherencia["taxonomy_coherence_score"]
                                )
                                if not reason:
                                    reason = "taxonomy_incoherent"
                                if coherencia["domain_coherence"] is False:
                                    reason = "domain_incoherent"
                                elif coherencia["category_coherence"] is False:
                                    reason = "category_incoherent"

                        if not can_help:
                            continue

                        proveedor_enriquecido = dict(proveedor)
                        proveedor_enriquecido["validation_confidence"] = confidence
                        proveedor_enriquecido["validation_reason"] = reason or None
                        proveedor_enriquecido["taxonomy_coherence_score"] = coherencia[
                            "taxonomy_coherence_score"
                        ]
                        proveedor_enriquecido["domain_coherence"] = coherencia[
                            "domain_coherence"
                        ]
                        proveedor_enriquecido["category_coherence"] = coherencia[
                            "category_coherence"
                        ]
                        proveedor_enriquecido["service_coherence"] = coherencia[
                            "service_coherence"
                        ]
                        proveedor_enriquecido["taxonomy_family_request"] = coherencia[
                            "taxonomy_family_request"
                        ]
                        proveedor_enriquecido["taxonomy_family_provider"] = coherencia[
                            "taxonomy_family_provider"
                        ]
                        proveedor_enriquecido["taxonomy_final_decision"] = coherencia[
                            "taxonomy_final_decision"
                        ]
                        if decision_data:
                            proveedor_enriquecido["validation_raw"] = {
                                key: decision_data.get(key)
                                for key in (
                                    "can_help",
                                    "confidence",
                                    "reason",
                                    "domain_coherence",
                                    "category_coherence",
                                    "service_coherence",
                                    "taxonomy_coherence_score",
                                )
                                if key in decision_data
                            }
                        proveedores_validados.append(proveedor_enriquecido)

                    self.logger.info(
                        "validator_final_pass_count passed=%s total=%s",
                        len(proveedores_validados),
                        len(proveedores),
                    )
                    return proveedores_validados

            proveedores_validados = []
            for proveedor, decision in zip(proveedores, lista_validacion):
                if isinstance(decision, bool):
                    can_help = decision
                    confidence = 1.0 if decision else 0.0
                    reason = "legacy_boolean_response"
                    decision_data = {}
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
                    decision_data = dict(decision or {})

                provider_service_text = " ".join(
                    part.strip()
                    for part in [
                        str(proveedor.get("matched_service_name") or "").strip(),
                        str(
                            proveedor.get("matched_service_summary")
                            or proveedor.get("service_summary")
                            or ""
                        ).strip(),
                        " ".join(
                            str(service).strip()
                            for service in (proveedor.get("services") or [])
                        ),
                    ]
                    if part.strip()
                )
                if self.validacion_proveedores_ia_only:
                    coherencia = {
                        "domain_coherence": decision_data.get("domain_coherence"),
                        "category_coherence": decision_data.get("category_coherence"),
                        "service_coherence": decision_data.get("service_coherence"),
                        "taxonomy_coherence_score": max(
                            0.0,
                            min(
                                1.0,
                                float(
                                    decision_data.get("taxonomy_coherence_score")
                                    or confidence
                                ),
                            ),
                        ),
                        "taxonomy_family_request": None,
                        "taxonomy_family_provider": None,
                        "taxonomy_final_decision": bool(can_help),
                    }
                else:
                    coherencia = self._evaluar_coherencia_taxonomica(
                        request_domain_code=dominio_request,
                        request_category_name=categoria_request,
                        request_service_text=" ".join(
                            part
                            for part in [
                                necesidad_usuario,
                                problema,
                            ]
                            if part
                        ),
                        provider_domain_code=proveedor.get("domain_code"),
                        provider_category_name=proveedor.get("category_name"),
                        provider_service_text=provider_service_text,
                    )

                    if not coherencia["taxonomy_final_decision"]:
                        can_help = False
                        confidence = min(
                            confidence, coherencia["taxonomy_coherence_score"]
                        )
                        if not reason:
                            reason = "taxonomy_incoherent"
                        if coherencia["domain_coherence"] is False:
                            reason = "domain_incoherent"
                        elif coherencia["category_coherence"] is False:
                            reason = "category_incoherent"

                if not can_help:
                    continue
                proveedor_enriquecido = dict(proveedor)
                proveedor_enriquecido["validation_confidence"] = confidence
                proveedor_enriquecido["validation_reason"] = reason or None
                proveedor_enriquecido["taxonomy_coherence_score"] = coherencia[
                    "taxonomy_coherence_score"
                ]
                proveedor_enriquecido["domain_coherence"] = coherencia[
                    "domain_coherence"
                ]
                proveedor_enriquecido["category_coherence"] = coherencia[
                    "category_coherence"
                ]
                proveedor_enriquecido["service_coherence"] = coherencia[
                    "service_coherence"
                ]
                proveedor_enriquecido["taxonomy_family_request"] = coherencia[
                    "taxonomy_family_request"
                ]
                proveedor_enriquecido["taxonomy_family_provider"] = coherencia[
                    "taxonomy_family_provider"
                ]
                proveedor_enriquecido["taxonomy_final_decision"] = coherencia[
                    "taxonomy_final_decision"
                ]
                if decision_data:
                    proveedor_enriquecido["validation_raw"] = {
                        key: decision_data.get(key)
                        for key in (
                            "can_help",
                            "confidence",
                            "reason",
                            "domain_coherence",
                            "category_coherence",
                            "service_coherence",
                            "taxonomy_coherence_score",
                        )
                        if key in decision_data
                    }
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
            self.logger.warning("⚠️ Timeout en validar_proveedores, fallback local")
            proveedores_fallback = [
                self._enriquecer_proveedor_timeout_fallback(
                    proveedor=proveedor,
                    necesidad_usuario=necesidad_usuario,
                    descripcion_problema=descripcion_problema,
                    request_domain_code=request_domain_code,
                    request_category_name=request_category_name,
                    request_domain=request_domain,
                    request_category=request_category,
                )
                for proveedor in proveedores
            ]
            self.logger.info(
                "validator_timeout_fallback passed=%s total=%s",
                len(proveedores_fallback),
                len(proveedores),
            )
            return proveedores_fallback
        except Exception as exc:
            self.logger.warning(f"⚠️ Error en validación IA, fail-closed: {exc}")
            return []

    MODELO_VALIDACION = (
        configuracion.modelo_validacion
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )
