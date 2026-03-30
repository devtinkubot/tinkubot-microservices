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
        if not (tokens & cls.TERMINOS_MUEBLES):
            return None
        if tokens & cls.VERBOS_RETAPIZADO:
            return "retapizado de muebles"
        if tokens & cls.VERBOS_LIMPIEZA:
            return "limpieza de muebles"
        if tokens & cls.VERBOS_RESTAURACION_MUEBLES:
            return "restauración de muebles"
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

        if not normalized_service:
            return None

        return {
            "normalized_service": normalized_service,
            "domain": domain or None,
            "category": category or None,
            "domain_code": cls._normalizar_codigo_taxonomia(domain),
            "category_name": cls._normalizar_categoria_taxonomia(category),
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
            "Extraer exactamente 3 campos de la necesidad del cliente:\n"
            "- normalized_service: La necesidad específica convertida a acción. "
            "En minúsculas, español neutro, de 4 a 10 palabras. "
            "Mantén términos técnicos si el usuario los usó (ej: pliegos, licitación).\n"
            "- domain: Área amplia (ej: 'tecnología', 'servicios legales').\n"
            "- category: Área específica (ej: 'gestión de proyectos de ti', "
            "'derecho penal').\n\n"
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
            '"category":"..."'
            "}"
        )

    @staticmethod
    def _construir_prompt_usuario_busqueda_cliente(texto_cliente: str) -> str:
        return (
            f'Convierte esta necesidad de usuario en un perfil de búsqueda: "{texto_cliente}"'
        )

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
                "domain": None,
                "category": None,
                "domain_code": None,
                "category_name": None,
            }

        servicio_local = self._resolver_servicio_por_reglas_locales(mensaje_usuario)
        if servicio_local:
            self.logger.info(
                "ℹ️ local_service_rule_detected input='%s' service='%s'",
                normalizar_texto_para_coincidencia(mensaje_usuario)[:120],
                servicio_local,
            )
            return {
                "normalized_service": servicio_local,
                "domain": None,
                "category": None,
                "domain_code": None,
                "category_name": None,
            }

        if not self.cliente_openai:
            self.logger.warning("⚠️ extraer_servicio_con_ia: sin cliente OpenAI")
            return None

        if not mensaje_usuario or not mensaje_usuario.strip():
            return None

        prompt_sistema = self._construir_prompt_sistema_busqueda_cliente()
        prompt_usuario = self._construir_prompt_usuario_busqueda_cliente(
            mensaje_usuario[:250]
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
                        response_format={"type": "json_object"},
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
            return perfil

        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout extrayendo servicio con IA")
            return None
        except Exception as exc:
            self.logger.warning(f"⚠️ Error extrayendo servicio con IA: {exc}")
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
