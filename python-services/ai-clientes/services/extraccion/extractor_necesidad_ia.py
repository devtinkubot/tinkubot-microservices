"""Extractor de necesidad y ciudad usando IA."""

import asyncio
import json
import logging
import re
import unicodedata
from typing import Any, Optional

from config.configuracion import configuracion
from openai import AsyncOpenAI
from utils.texto import normalizar_texto_para_coincidencia


class ExtractorNecesidadIA:
    """Servicio de extracción semántica de servicio y ciudad con IA."""

    PALABRAS_VAGAS_OCUPACION = {
        "necesito",
        "busco",
        "quiero",
        "requiero",
        "ocupo",
        "solicito",
        "contratar",
        "contactar",
        "un",
        "una",
        "unos",
        "unas",
        "el",
        "la",
        "los",
        "las",
        "de",
        "del",
        "para",
        "por",
        "favor",
        "con",
        "urgente",
        "urgentemente",
        "ayuda",
        "alguien",
        "que",
        "me",
        "pueda",
    }

    # Modelos desde configuración centralizada
    MODELO_EXTRACCION = (
        configuracion.modelo_extraccion
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )
    MODELO_NORMALIZACION = (
        configuracion.modelo_normalizacion
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )

    # Sinónimos de ciudades de Ecuador para normalización local
    SINONIMOS_CIUDADES_ECUADOR = {
        "Quito": {"quito"},
        "Guayaquil": {"guayaquil"},
        "Cuenca": {"cuenca", "cueca"},
        "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
        "Manta": {"manta"},
        "Portoviejo": {"portoviejo"},
        "Machala": {"machala"},
        "Durán": {"duran", "durán"},
        "Loja": {"loja"},
        "Ambato": {"ambato"},
        "Riobamba": {"riobamba"},
        "Esmeraldas": {"esmeraldas"},
        "Quevedo": {"quevedo"},
        "Babahoyo": {"babahoyo", "baba hoyo"},
        "Milagro": {"milagro"},
        "Ibarra": {"ibarra"},
        "Tulcán": {"tulcan", "tulcán"},
        "Latacunga": {"latacunga"},
        "Salinas": {"salinas"},
    }
    VERBOS_RESTAURACION_MUEBLES = {
        "arreglar",
        "reparar",
        "restaurar",
        "restauracion",
        "remodelar",
        "remodelacion",
        "renovar",
    }
    VERBOS_RETAPIZADO = {
        "tapizar",
        "retapizar",
        "tapiceria",
        "tapicería",
        "forrar",
    }
    VERBOS_LIMPIEZA = {
        "limpiar",
        "lavar",
        "desmanchar",
    }
    VERBOS_JARDINERIA = {
        "podar",
        "poda",
        "cortar",
        "recortar",
        "desmalezar",
        "desbrozar",
        "arreglar",
        "mantener",
        "mantenimiento",
    }
    TERMINOS_MANTENIMIENTO_JARDIN = {
        "sucio",
        "sucia",
        "sucios",
        "sucias",
        "limpiar",
        "limpieza",
        "ordenar",
        "desorden",
        "desordenado",
        "desordenada",
        "cuidado",
    }
    TERMINOS_MUEBLES = {
        "mueble",
        "muebles",
        "mesa",
        "mesas",
        "silla",
        "sillas",
        "comedor",
        "sala",
        "sofa",
        "sofas",
        "sillon",
        "sillones",
        "ropero",
        "armario",
        "aparador",
        "vitrina",
    }
    TERMINOS_JARDIN = {
        "jardin",
        "jardines",
        "cesped",
        "césped",
        "grama",
        "pasto",
        "seto",
        "setos",
        "arbusto",
        "arbustos",
        "plantas",
        "planta",
        "huerto",
        "area verde",
        "área verde",
    }

    def __init__(
        self,
        cliente_openai: Optional[AsyncOpenAI],
        semaforo_openai: Optional[asyncio.Semaphore],
        tiempo_espera_openai: float,
        logger: logging.Logger,
    ):
        self.cliente_openai = cliente_openai
        self.semaforo_openai = semaforo_openai
        self.tiempo_espera_openai = tiempo_espera_openai
        self.logger = logger

    @classmethod
    def _normalizar_texto_local(cls, texto: str) -> str:
        base = unicodedata.normalize("NFD", (texto or "").strip().lower())
        sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
        return re.sub(r"\s+", " ", limpio).strip()

    @classmethod
    def _tokens_relevantes(cls, texto: str) -> list[str]:
        return [
            token
            for token in cls._normalizar_texto_local(texto).split()
            if token and token not in cls.PALABRAS_VAGAS_OCUPACION
        ]

    @classmethod
    def _extraer_hint_ocupacion_generica(cls, texto: str) -> Optional[str]:
        tokens = cls._tokens_relevantes(texto)
        # Solo tratamos como ocupación genérica las solicitudes de una sola palabra.
        # Frases de dos o más palabras como "asesor contable" deben avanzar
        # para que el extractor las normalice y el flujo llegue a búsqueda.
        if len(tokens) != 1:
            return None
        return " ".join(tokens)

    @classmethod
    def _resolver_servicio_por_reglas_locales(
        cls, mensaje_usuario: str
    ) -> Optional[str]:
        texto_norm = cls._normalizar_texto_local(mensaje_usuario)
        tokens = set(texto_norm.split())
        if tokens & cls.TERMINOS_MUEBLES:
            if tokens & cls.VERBOS_RETAPIZADO:
                return "retapizado de muebles"
            if tokens & cls.VERBOS_LIMPIEZA:
                return "limpieza de muebles"
            if tokens & cls.VERBOS_RESTAURACION_MUEBLES:
                return "restauración de muebles"
        if tokens & cls.TERMINOS_JARDIN:
            if tokens & cls.TERMINOS_MANTENIMIENTO_JARDIN:
                return "mantenimiento de jardines"
            if tokens & cls.VERBOS_JARDINERIA:
                return "poda de jardines"
            return "mantenimiento de jardines"
        return None

    @classmethod
    def _normalizar_codigo_taxonomia(cls, texto: Optional[str]) -> Optional[str]:
        valor = cls._normalizar_texto_local(texto or "")
        if not valor:
            return None
        return re.sub(r"\s+", "_", valor).strip("_") or None

    @classmethod
    def _normalizar_categoria_taxonomia(cls, texto: Optional[str]) -> Optional[str]:
        valor = cls._normalizar_texto_local(texto or "")
        return valor or None

    @classmethod
    def _extraer_senales_busqueda(
        cls,
        mensaje_usuario: str,
        normalized_service: str,
        service_summary: Optional[str],
        domain: Optional[str],
        category: Optional[str],
    ) -> list[str]:
        texto_norm = cls._normalizar_texto_local(mensaje_usuario)
        tokens = texto_norm.split()
        senales: list[str] = []

        if service_summary:
            senales.append(f"resumen del servicio: {service_summary}")
        if normalized_service:
            senales.append(f"servicio objetivo: {normalized_service}")
        if domain:
            senales.append(f"dominio: {domain}")
        if category:
            senales.append(f"categoría: {category}")

        if any(token in {"urgente", "urgentemente"} for token in tokens):
            senales.append("requiere atención urgente")

        if any(
            token in {"problema", "falla", "rota", "dañada", "dañado"}
            for token in tokens
        ):
            senales.append("describe un problema concreto")

        if any(
            token in {"necesito", "busco", "quiero", "requiero", "solicito"}
            for token in tokens
        ):
            senales.append("solicita un servicio específico")

        vistos: set[str] = set()
        resultado: list[str] = []
        for senal in senales:
            limpio = " ".join(str(senal or "").strip().split())
            if not limpio:
                continue
            normalizado = cls._normalizar_texto_local(limpio)
            if normalizado in vistos:
                continue
            vistos.add(normalizado)
            resultado.append(limpio)
        return resultado

    @classmethod
    def _normalizar_senales(cls, senales: Optional[list[str]]) -> list[str]:
        resultado: list[str] = []
        vistos: set[str] = set()
        for senal in senales or []:
            limpio = " ".join(str(senal or "").strip().split())
            if not limpio:
                continue
            normalizado = cls._normalizar_texto_local(limpio)
            if normalizado in vistos:
                continue
            vistos.add(normalizado)
            resultado.append(limpio)
        return resultado

    @classmethod
    def _armar_search_profile(
        cls,
        *,
        raw_input: Optional[str],
        primary_service: Optional[str],
        service_summary: Optional[str] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        signals: Optional[list[str]] = None,
        confidence: float = 0.0,
        source: str = "client",
    ) -> dict[str, Any]:
        servicio = str(primary_service or "").strip()
        resumen = str(service_summary or "").strip() or None
        dominio = str(domain or "").strip() or None
        categoria = str(category or "").strip() or None
        senales_procesadas = cls._normalizar_senales(signals)
        if not senales_procesadas:
            if resumen:
                senales_procesadas.append(f"resumen del servicio: {resumen}")
            if servicio:
                senales_procesadas.append(f"servicio objetivo: {servicio}")
            if dominio:
                senales_procesadas.append(f"dominio: {dominio}")
            if categoria:
                senales_procesadas.append(f"categoría: {categoria}")
        return {
            "raw_input": (raw_input or "").strip(),
            "primary_service": servicio or None,
            "service_summary": resumen,
            "domain": dominio,
            "category": categoria,
            "signals": senales_procesadas,
            "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
            "source": source,
        }

    @classmethod
    def _construir_search_profile(
        cls,
        *,
        raw_input: str,
        normalized_service: str,
        service_summary: Optional[str] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        confidence: float = 0.0,
    ) -> dict[str, Any]:
        return cls._armar_search_profile(
            raw_input=raw_input,
            primary_service=normalized_service,
            service_summary=service_summary,
            domain=domain,
            category=category,
            signals=cls._extraer_senales_busqueda(
                raw_input,
                normalized_service,
                service_summary,
                domain,
                category,
            ),
            confidence=confidence,
        )

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

        for candidato in candidatos:
            try:
                return json.loads(candidato)
            except json.JSONDecodeError:
                continue
        return None

    @classmethod
    def _normalizar_respuesta_busqueda_cliente(
        cls, data: Any
    ) -> Optional[dict[str, Optional[str]]]:
        if not isinstance(data, dict):
            return None

        status = str(data.get("status") or "").strip().lower() or None

        normalized_service = (
            str(
                data.get("normalized_service")
                or data.get("service")
                or data.get("service_name")
                or ""
            )
            .strip()
        )
        domain = (
            str(data.get("domain") or data.get("domain_code") or "").strip()
        )
        category = (
            str(data.get("category") or data.get("category_name") or "").strip()
        )

        service_summary = str(data.get("service_summary") or "").strip() or None
        confidence = data.get("confidence")
        reason = str(data.get("reason") or "").strip() or None

        if not normalized_service:
            return None

        return {
            "normalized_service": normalized_service,
            "domain": domain or None,
            "category": category or None,
            "domain_code": cls._normalizar_codigo_taxonomia(domain),
            "category_name": cls._normalizar_categoria_taxonomia(category),
            "service_summary": service_summary,
            "confidence": confidence,
            "reason": reason,
            "status": status,
        }

    @classmethod
    def _construir_prompt_sistema_busqueda_cliente(cls) -> str:
        return (
            "Eres un experto en entender necesidades de clientes en Ecuador "
            "y traducirlas a perfiles de búsqueda semántica.\n\n"
            "MARCO DE REFERENCIA (Lógica UNSPSC): "
            "Usa la jerarquía mental del estándar UNSPSC para deducir el dominio "
            "y la categoría de la necesidad del usuario, pero NUNCA uses códigos, "
            "solo texto.\n\n"
            "TU TAREA:\n"
            "Extraer los campos operativos del servicio solicitado por el cliente.\n"
            "- normalized_service: La necesidad específica convertida a acción. "
            "En minúsculas, español neutro, de 4 a 10 palabras. "
            "Mantén términos técnicos si el usuario los usó (ej: pliegos, licitación).\n"
            "- domain: Área amplia (ej: 'tecnología', 'servicios legales').\n"
            "- category: Área específica (ej: 'gestión de proyectos de ti', "
            "'derecho penal').\n"
            "- service_summary: Resumen breve y operativo del servicio.\n"
            "- confidence: 0.0 a 1.0.\n"
            "- reason: Justificación breve.\n"
            "- status: accepted|clarification_required|rejected.\n\n"
            "REGLAS CRÍTICAS:\n"
            "1. ANTI-PROFESIÓN: Si el usuario pide un oficio genérico "
            "(ej: 'necesito un abogado' o 'busco carpintero'), "
            "NO pongas el oficio en normalized_service. Pon la acción "
            "('asesoría legal', 'carpintería de madera').\n"
            "2. ESPECIFICIDAD: Prioriza lo más específico sobre lo general.\n"
            "3. MULTIPLES NECESIDADES: Si el usuario pide varias cosas distintas "
            "no relacionadas, elige la que tenga más peso o detalle en su frase.\n"
            "4. No uses términos en inglés.\n\n"
            "Responde SOLO con este JSON:\n"
            "{"
            '"normalized_service":"...",'
            '"domain":"...",'
            '"category":"...",'
            '"service_summary":"...",'
            '"confidence":0.0,'
            '"reason":"...",'
            '"status":"accepted|clarification_required|rejected"'
            "}"
        )

    @staticmethod
    def _construir_prompt_usuario_busqueda_cliente(
        texto_cliente: str,
        *,
        normalized_service_hint: Optional[str] = None,
        modo_estricto: bool = False,
    ) -> str:
        lineas = [
            f'Convierte esta necesidad de usuario en un perfil de búsqueda: "{texto_cliente}"',
        ]
        if normalized_service_hint:
            lineas.append(
                "Servicio normalizado sugerido por reglas locales: "
                f'"{normalized_service_hint}"'
            )
        if modo_estricto:
            lineas.append(
                "Modo estricto: si el texto describe un servicio real, "
                "debes completar domain y category. Si no puedes hacerlo, "
                "responde clarification_required."
            )
        return "\n".join(lineas)

    async def _clasificar_servicio_busqueda_cliente(
        self,
        mensaje_usuario: str,
        *,
        normalized_service_hint: Optional[str] = None,
        modo_estricto: bool = False,
    ) -> Optional[dict[str, Optional[str]]]:
        if not self.cliente_openai:
            return None

        prompt_sistema = self._construir_prompt_sistema_busqueda_cliente()
        if modo_estricto:
            prompt_sistema += (
                "\n\nREGLAS ESTRICTAS:\n"
                "- Debes cerrar domain y category cuando el texto sea resoluble.\n"
                "- No devuelvas profesiones puras como normalized_service.\n"
                "- Si el texto sigue siendo ambiguo, usa clarification_required.\n"
            )

        prompt_usuario = self._construir_prompt_usuario_busqueda_cliente(
            mensaje_usuario[:250],
            normalized_service_hint=normalized_service_hint,
            modo_estricto=modo_estricto,
        )

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_EXTRACCION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "service_classification",
                                "strict": True,
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "normalized_service": {"type": "string"},
                                        "domain": {"type": ["string", "null"]},
                                        "category": {"type": ["string", "null"]},
                                        "service_summary": {"type": ["string", "null"]},
                                        "confidence": {"type": "number"},
                                        "reason": {"type": "string"},
                                        "status": {
                                            "type": "string",
                                            "enum": [
                                                "accepted",
                                                "clarification_required",
                                                "rejected",
                                            ],
                                        },
                                    },
                                    "required": [
                                        "normalized_service",
                                        "domain",
                                        "category",
                                        "service_summary",
                                        "confidence",
                                        "reason",
                                        "status",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        temperature=0.0,
                        max_tokens=120,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                return None

            contenido = (respuesta.choices[0].message.content or "").strip()
            payload = self._extraer_json_parseable(contenido)
            perfil = self._normalizar_respuesta_busqueda_cliente(payload)
            if not perfil:
                self.logger.warning(
                    "⚠️ Respuesta de IA de búsqueda inválida: %s",
                    contenido[:200],
                )
                return None

            self.logger.info(
                "✅ IA detectó perfil: service='%s', domain='%s', category='%s' de: '%s...'",
                perfil["normalized_service"],
                perfil.get("domain"),
                perfil.get("category"),
                mensaje_usuario[:50],
            )
            confidence = perfil.get("confidence")
            if not isinstance(confidence, (int, float)) or float(confidence) <= 0.0:
                confidence = 0.92 if perfil.get("domain") and perfil.get("category") else 0.75
            perfil["search_profile"] = self._construir_search_profile(
                raw_input=mensaje_usuario,
                normalized_service=perfil["normalized_service"] or "",
                service_summary=perfil.get("service_summary"),
                domain=perfil.get("domain"),
                category=perfil.get("category"),
                confidence=float(confidence),
            )
            return perfil
        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo servicio con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo servicio con IA: {exc}")
            return None

    async def _normalizar_servicio_a_espanol(
        self, servicio_detectado: str
    ) -> Optional[str]:
        """Normaliza un servicio detectado a español neutro usando IA."""
        if not self.cliente_openai:
            return servicio_detectado

        servicio_base = (servicio_detectado or "").strip()
        if not servicio_base:
            return servicio_detectado

        prompt_sistema = """Convierte nombres de servicios profesionales a
español neutro sin perder especificidad.

Reglas:
- Si ya está en español, conserva la idea principal.
- Si está en otro idioma, tradúcelo al español.
- Mantén un subservicio específico
  (ej: "elaboración de pliegos de contratación pública").
- Evita generalizar a categorías paraguas
  (ej: "asesoría legal", "marketing digital") cuando haya detalle.
- Devuelve una frase corta (4 a 10 palabras), en minúsculas.
- No agregues explicaciones.

Responde SOLO con el nombre del servicio."""

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_NORMALIZACION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": servicio_base[:120]},
                        ],
                        temperature=0.0,
                        max_tokens=40,
                    ),
                    timeout=self.tiempo_espera_openai,
                )
            if not respuesta.choices:
                return servicio_detectado

            servicio_es = (respuesta.choices[0].message.content or "").strip()
            servicio_es = servicio_es.strip('"').strip("'").strip()
            return servicio_es or servicio_detectado
        except Exception as exc:
            self.logger.warning(f"⚠️ Error normalizando servicio a español: {exc}")
            return servicio_detectado

    async def extraer_servicio_con_ia(
        self, mensaje_usuario: str
    ) -> Optional[dict[str, Optional[str]]]:
        """Extrae el perfil de búsqueda requerido por el cliente usando IA."""
        hint_ocupacion = self._extraer_hint_ocupacion_generica(mensaje_usuario)
        if hint_ocupacion:
            self.logger.info(
                "ℹ️ occupation_hint_detected input='%s' hint='%s'",
                normalizar_texto_para_coincidencia(mensaje_usuario)[:120],
                hint_ocupacion,
            )
            return {
                "normalized_service": hint_ocupacion,
                "service_summary": hint_ocupacion,
                "domain": None,
                "category": None,
                "domain_code": None,
                "category_name": None,
                "search_profile": self._construir_search_profile(
                    raw_input=mensaje_usuario,
                    normalized_service=hint_ocupacion,
                    service_summary=hint_ocupacion,
                    domain=None,
                    category=None,
                ),
            }

        servicio_local = self._resolver_servicio_por_reglas_locales(mensaje_usuario)
        if servicio_local:
            self.logger.info(
                "ℹ️ local_service_rule_detected input='%s' service='%s'",
                normalizar_texto_para_coincidencia(mensaje_usuario)[:120],
                servicio_local,
            )
        if not self.cliente_openai:
            if servicio_local:
                return {
                    "normalized_service": servicio_local,
                    "service_summary": servicio_local,
                    "domain": None,
                    "category": None,
                    "domain_code": None,
                    "category_name": None,
                    "search_profile": self._construir_search_profile(
                        raw_input=mensaje_usuario,
                        normalized_service=servicio_local,
                        service_summary=servicio_local,
                        domain=None,
                        category=None,
                    ),
                }
            self.logger.warning("⚠️ extraer_servicio_con_ia: sin cliente OpenAI")
            return None

        if not mensaje_usuario or not mensaje_usuario.strip():
            return None

        perfil = await self._clasificar_servicio_busqueda_cliente(
            mensaje_usuario,
            normalized_service_hint=servicio_local,
            modo_estricto=False,
        )

        if perfil and (not perfil.get("domain") or not perfil.get("category")):
            perfil_estricto = await self._clasificar_servicio_busqueda_cliente(
                mensaje_usuario,
                normalized_service_hint=perfil.get("normalized_service")
                or servicio_local,
                modo_estricto=True,
            )
            if perfil_estricto:
                perfil = perfil_estricto

        if perfil:
            return perfil

        if servicio_local:
            return {
                "normalized_service": servicio_local,
                "service_summary": servicio_local,
                "domain": None,
                "category": None,
                "domain_code": None,
                "category_name": None,
                "search_profile": self._construir_search_profile(
                    raw_input=mensaje_usuario,
                    normalized_service=servicio_local,
                    service_summary=servicio_local,
                    domain=None,
                    category=None,
                ),
            }
        return None

    async def extraer_servicio_con_ia_pura(
        self,
        mensaje_usuario: str,
    ) -> Optional[dict[str, Optional[str]]]:
        """Alias de compatibilidad para extraer servicio con IA."""
        return await self.extraer_servicio_con_ia(mensaje_usuario)

    async def es_necesidad_o_problema(self, mensaje_usuario: str) -> bool:
        """
        Determina si el mensaje describe una necesidad/problema concreto.

        Fail-open: si no hay cliente OpenAI o falla la llamada, retorna True para
        no bloquear el flujo por indisponibilidad del proveedor IA.
        """
        texto = (mensaje_usuario or "").strip()
        if not texto:
            return False

        if self._extraer_hint_ocupacion_generica(texto):
            self.logger.info(
                "ℹ️ gate_rejected_local_hint normalized_input='%s'",
                normalizar_texto_para_coincidencia(texto)[:120],
            )
            return False

        tokens = self._tokens_relevantes(texto)
        if tokens:
            verbos_solicitud = {
                "necesito",
                "necesita",
                "necesitan",
                "busco",
                "quiero",
                "requiero",
                "requiere",
                "requerimos",
                "solicito",
                "contratar",
                "contrato",
            }
            if tokens[0] in verbos_solicitud and len(tokens) >= 2:
                return True

        if not self.cliente_openai:
            return True

        prompt_sistema = """Clasifica si el mensaje del usuario describe
una necesidad/problema concreto.

Responde SOLO "si" o "no".

Responde "si" cuando:
- Explica qué pasó, qué necesita resolver o qué quiere lograr.
- También responde "si" cuando el usuario pide contratar o encontrar
  un servicio de forma explícita, por ejemplo:
  "necesito un asesor contable", "requiere un administrador de proyectos",
  "busco un abogado".
- Ejemplos: "mi lavadora no enciende", "necesito arreglar una tubería rota".

Responde "no" cuando:
- Es solo una profesión/rol o palabra suelta sin contexto de problema.
- Ejemplos: "plomero", "abogado", "electricista", "hola"."""
        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_NORMALIZACION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": texto[:250]},
                        ],
                        temperature=0.0,
                        max_tokens=5,
                    ),
                    timeout=self.tiempo_espera_openai,
                )
            if not respuesta.choices:
                return True

            decision = (respuesta.choices[0].message.content or "").strip().lower()
            es_necesidad = decision.startswith("si") or decision.startswith("sí")
            if not es_necesidad:
                self.logger.info(
                    "ℹ️ gate_rejected necesidad: normalized_input='%s'",
                    normalizar_texto_para_coincidencia(texto)[:120],
                )
            return es_necesidad
        except Exception as exc:
            self.logger.warning(
                "⚠️ Error validando necesidad/problema con IA (fail-open): %s",
                exc,
            )
            return True

    async def extraer_ubicacion_con_ia(self, texto: str) -> Optional[str]:
        """Extrae la ciudad del texto usando IA."""
        ciudades = [
            "Quito",
            "Guayaquil",
            "Cuenca",
            "Santo Domingo",
            "Manta",
            "Portoviejo",
            "Machala",
            "Durán",
            "Loja",
            "Ambato",
            "Riobamba",
            "Esmeraldas",
        ]

        ciudades_str = ", ".join(ciudades)

        if not self.cliente_openai:
            return None

        prompt_sistema = f"""Eres un experto en identificar ciudades de Ecuador.
Tu tarea es extraer LA CIUDAD mencionada en el texto.

Ciudades válidas: {ciudades_str}

Reglas:
1. Responde SOLO con el nombre de la ciudad si está en la lista
2. Si no se menciona ninguna ciudad válida, responde "null"
3. Normaliza el nombre (ej: "quito" → "Quito")

Ejemplos:
- "en Quito" → "Quito"
- "lo necesito en cuenca" → "Cuenca"
- "para guayaquil" → "Guayaquil"
- "en mi ciudad" → "null"

Responde SOLO con el nombre de la ciudad o "null", sin explicaciones."""

        prompt_usuario = f'¿Qué ciudad de Ecuador se menciona en: "{texto[:200]}"'

        try:
            async with self.semaforo_openai:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_NORMALIZACION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.3,
                        max_tokens=30,
                    ),
                    timeout=self.tiempo_espera_openai,
                )

            if not respuesta.choices:
                return None

            ubicacion = (respuesta.choices[0].message.content or "").strip()
            ubicacion = ubicacion.strip('"').strip("'").strip()

            if ubicacion.lower() == "null" or not ubicacion:
                return None

            for ciudad in ciudades:
                if ciudad.lower() == ubicacion.lower():
                    self.logger.info(
                        "✅ IA extrajo ciudad: '%s' del texto: '%s...'",
                        ciudad,
                        texto[:50],
                    )
                    return ciudad

            return None

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo ciudad con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo ciudad con IA: {exc}")
            return None

    async def _extraer_ubicacion_con_ia(self, texto: str) -> Optional[str]:
        """Alias de compatibilidad para extracción de ciudad con IA."""
        return await self.extraer_ubicacion_con_ia(texto)
