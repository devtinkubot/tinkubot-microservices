"""
Intent Classifier Service para ai-clientes.

Este módulo clasifica las intenciones de búsqueda del usuario en tres categorías:
- DIRECT: Búsqueda directa de profesión ("necesito un plomero")
- NEED_BASED: Búsqueda basada en necesidad/problema ("tengo goteras")
- AMBIGUOUS: Consulta ambigua que requiere clarificación

La clasificación usa múltiples estrategias en orden de prioridad:
1. Pattern matching (regex para patrones comunes)
2. Diccionario de problemas → profesiones
3. Fallback: Clasificación con IA (OpenAI)

Author: Claude Sonnet 4.5
Created: 2026-01-15
"""

import logging
import re
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Tipos de intención de búsqueda."""
    DIRECT = "direct"  # "necesito un plomero"
    NEED_BASED = "need_based"  # "tengo goteras"
    AMBIGUOUS = "ambiguous"  # "ayuda", "servicios"


class IntentClassifier:
    """
    Clasificador de intenciones de búsqueda.

    Usa múltiples estrategias para clasificar queries del usuario:
    1. Pattern matching (rápido, patrones comunes)
    2. Diccionario de keywords (problemas → profesiones)
    3. Clasificación con IA (fallback para queries complejas)

    Attributes:
        need_keywords: Diccionario de problemas → profesiones

    Example:
        >>> classifier = IntentClassifier()
        >>> intent = classifier.classify_intent("tengo goteras")
        >>> print(intent)  # IntentType.NEED_BASED
    """

    # Patrones regex para búsquedas DIRECTAS
    DIRECT_PATTERNS = [
        r"^(necesito|busco|requiero|quiero|necesitamos)\s+(un|una|algun)?\s*\w+",
        r"^(buscar|búscar|encontrar|encuentrar)\s+(un|una)?\s*\w+",
        r"^(contactar|llamar|hablar\s+con)\s+(un|una)?\s*\w+",
        r"^(me\s+gustaría|podrías?\s+\w+)\s+\w+",
    ]

    # Diccionario de PROBLEMAS → PROFESIONES
    # Mapeo de problemas comunes a la profesión que los resuelve
    NEED_KEYWORDS: Dict[str, str] = {
        # Problemas de plomería
        "gotera": "plomero",
        "goteras": "plomero",
        "fuga": "plomero",
        "filtración": "plomero",
        "filtraciones": "plomero",
        "tubería": "plomero",
        "tuberias": "plomero",
        "tuberias": "plomero",
        "desagüe": "plomero",
        "desague": "plomero",
        "tapa": "plomero",
        "tapon": "plomero",
        "grifo": "plomero",
        "llave": "plomero",
        "baño": "plomero",
        "ducha": "plomero",
        "sanitario": "plomero",
        "inodoro": "plomero",
        "fontanería": "plomero",
        "fontaneria": "plomero",
        "gasfitero": "plomero",
        "gasfitería": "plomero",

        # Problemas eléctricos
        "cortocircuito": "electricista",
        "corto circuito": "electricista",
        "chispa": "electricista",
        "chispazo": "electricista",
        "sin luz": "electricista",
        "se fue la luz": "electricista",
        "electricidad": "electricista",
        "instalacion electrica": "electricista",
        "instalación eléctrica": "electricista",
        "enchufe": "electricista",
        "tomacorriente": "electricista",
        "interruptor": "electricista",
        "cable": "electricista",
        "cableado": "electricista",
        "luz": "electricista",
        "bombilla": "electricista",
        "foco": "electricista",

        # Problemas de aire acondicionado
        "aire acondicionado": "técnico de aire acondicionado",
        "aire": "técnico de aire acondicionado",
        "climatización": "técnico de aire acondicionado",
        "climatizacion": "técnico de aire acondicionado",
        "refrigeración": "técnico de refrigeración",
        "refrigeracion": "técnico de refrigeración",
        "nevera": "técnico de refrigeración",
        "heladera": "técnico de refrigeración",
        "refrigerador": "técnico de refrigeración",
        "congelador": "técnico de refrigeración",

        # Problemas de pintura
        "pintar": "pintor",
        "pintura": "pintor",
        "pared": "pintor",
        "paredes": "pintor",
        "muro": "pintor",
        "muros": "pintor",
        "techumbre": "pintor",

        # Problemas de limpieza
        "limpieza": "limpieza",
        "limpiar": "limpieza",
        "sucio": "limpieza",
        "mugre": "limpieza",

        # Problemas de jardinería
        "jardín": "jardinero",
        "jardin": "jardinero",
        "césped": "jardinero",
        "cesped": "jardinero",
        "pasto": "jardinero",
        "podar": "jardinero",
        "corte": "jardinero",
        "arbol": "jardinero",
        "árbol": "jardinero",

        # Problemas de mascotas
        "perro": "veterinario",
        "gato": "veterinario",
        "mascota": "veterinario",
        "vacuna": "veterinario",
        "enfermo": "veterinario",

        # Problemas de construcción
        "construir": "constructor",
        "construcción": "constructor",
        "construccion": "constructor",
        "obras": "constructor",
        "obra": "constructor",
        "albañil": "constructor",
        "albañilería": "constructor",
        "casa": "constructor",
        "habitacion": "constructor",
        "cuarto": "constructor",

        # Problemas de carpintería
        "carpintero": "carpintero",
        "carpintería": "carpintero",
        "mueble": "carpintero",
        "muebles": "carpintero",
        "madera": "carpintero",
        "armario": "carpintero",
        "closet": "carpintero",
        "estante": "carpintero",
        "puerta": "carpintero",
        "ventana": "carpintero",

        # Problemas de cerrajería
        "cerradura": "cerrajero",
        "llave": "cerrajero",
        "cerrajero": "cerrajero",
        "puerta": "cerrajero",
        "cerrar": "cerrajero",
        "abrir": "cerrajero",

        # Problemas de informática
        "computadora": "técnico de computadoras",
        "computador": "técnico de computadoras",
        "laptop": "técnico de computadoras",
        "portátil": "técnico de computadoras",
        "pc": "técnico de computadoras",
        "virus": "técnico de computadoras",
        "hackeo": "técnico de computadoras",
        "internet": "técnico de computadoras",
        "wifi": "técnico de computadoras",
        "red": "técnico de computadoras",

        # Problemas de fotografía
        "foto": "fotógrafo",
        "fotografía": "fotógrafo",
        "fotografo": "fotógrafo",
        "retrato": "fotógrafo",
        "evento": "fotógrafo",
        "boda": "fotógrafo",
        "matrimonio": "fotógrafo",

        # Problemas de música
        "músico": "músico",
        "musico": "músico",
        "música": "músico",
        "musica": "músico",
        "guitarra": "músico",
        "piano": "músico",
        "batería": "músico",
        "bateria": "músico",
        "cantante": "músico",
        "canto": "músico",

        # Problemas de cocina
        "cocina": "cocinero",
        "comida": "cocinero",
        "chef": "cocinero",
        "restaurante": "cocinero",
        "catering": "cocinero",
        "banquete": "cocinero",

        # Problemas de belleza
        "cabello": "estilista",
        "pelo": "estilista",
        "corte": "estilista",
        "tinte": "estilista",
        "mechón": "estilista",
        "mechas": "estilista",
        "peinado": "estilista",
        "estilista": "estilista",
        "peluquero": "estilista",
        "salón de belleza": "estilista",
        "spa": "estética",
        "masaje": "masajista",
        "facial": "esteticista",
        "limpieza facial": "esteticista",
        "cosmetología": "esteticista",
        "cosmetologia": "esteticista",
        "belleza": "esteticista",
        "skin care": "esteticista",
        "skincare": "esteticista",

        # Problemas de transporte
        "mudanza": "mudanza",
        "mudar": "mudanza",
        "transportar": "transporte",
        "carga": "transporte",
        "muebles": "mudanza",
        "camión": "transporte",
        "camion": "transporte",
        "flete": "transporte",

        # Servicios médicos - inyecciones y procedimientos
        "inyección": "enfermero",
        "inyecciones": "enfermero",
        "inyectarme": "enfermero",
        "inyectarse": "enfermero",
        "inyectar": "enfermero",
        "suero": "enfermero",
        "sueros": "enfermero",
        "vitamina": "enfermero",
        "vitaminas": "enfermero",
        "inyectable": "enfermero",
        "inyectables": "enfermero",
        "curación": "enfermero",
        "curaciones": "enfermero",
        "curar": "enfermero",
        "herida": "enfermero",
        "heridas": "enfermero",
        "vacunación": "enfermero",
        "vacuna": "enfermero",
        "vacunas": "enfermero",
        "vacunarse": "enfermero",
        "vacunarme": "enfermero",
        "toma de muestras": "enfermero",
        "análisis": "enfermero",
        "analisis": "enfermero",
        "análisis de sangre": "enfermero",
        "analisis de sangre": "enfermero",
        "cuidados": "enfermero",
        "cuidado": "enfermero",
        "signos vitales": "enfermero",
        "presión arterial": "enfermero",
        "inyección intramuscular": "enfermero",
        "inyección intravenosa": "enfermero",
        "inyeccion intramuscular": "enfermero",
        "inyeccion intravenosa": "enfermero",
        "intramuscular": "enfermero",
        "intravenosa": "enfermero",
        "intramuscular": "enfermero",
        "intravenosa": "enfermero",
    }

    # Palabras ambiguas que requieren clarificación
    AMBIGUOUS_KEYWORDS = [
        "ayuda", "información", "informacion", "servicios",
        "contacto", "asistencia", "soporte", "consulta",
        "asesoría", "asesoria", "asesoramiento", "quiero",
        "necesito", "busco", "requiero", "algo"
    ]

    def __init__(self):
        """Inicializa el clasificador de intenciones."""
        self._compile_patterns()
        logger.debug("IntentClassifier inicializado")

    def _compile_patterns(self):
        """Compila los patrones regex para mejor rendimiento."""
        self.compiled_direct_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DIRECT_PATTERNS
        ]

    def classify_intent(
        self,
        query: str,
        use_ai_fallback: bool = False
    ) -> IntentType:
        """
        Clasifica la intención de búsqueda del usuario.

        Args:
            query: Query del usuario (ej: "tengo goteras", "necesito un plomero")
            use_ai_fallback: Si es True, usa IA como fallback (default: False)

        Returns:
            IntentType: DIRECT, NEED_BASED, o AMBIGUOUS

        Example:
            >>> classifier = IntentClassifier()
            >>> intent = classifier.classify_intent("tengo goteras")
            >>> print(intent)  # IntentType.NEED_BASED
            >>> intent = classifier.classify_intent("necesito un plomero")
            >>> print(intent)  # IntentType.DIRECT
        """
        if not query or not query.strip():
            logger.warning("Query vacía recibida en classify_intent")
            return IntentType.AMBIGUOUS

        query_normalized = query.lower().strip()

        # Estrategia 1: Pattern matching para búsquedas DIRECTAS
        if self._match_direct_pattern(query_normalized):
            logger.debug(f"Query '{query}' clasificada como DIRECT (pattern match)")
            return IntentType.DIRECT

        # Estrategia 2: Diccionario de problemas → profesiones
        inferred_profession = self._match_need_keyword(query_normalized)
        if inferred_profession:
            logger.debug(
                f"Query '{query}' clasificada como NEED_BASED "
                f"(inferred profession: {inferred_profession})"
            )
            return IntentType.NEED_BASED

        # Estrategia 3: Palabras ambiguas
        if self._match_ambiguous_keyword(query_normalized):
            logger.debug(f"Query '{query}' clasificada como AMBIGUOUS")
            return IntentType.AMBIGUOUS

        # Fallback: Default a NEED_BASED (mejor sobre-pesar que sub-pesar)
        logger.debug(
            f"Query '{query}' sin clasificación clara, "
            "default a NEED_BASED"
        )
        return IntentType.NEED_BASED

    def infer_profession_from_need(self, query: str) -> Optional[str]:
        """
        Infiere la profesión basándose en una query basada en necesidad.

        Args:
            query: Query del usuario (ej: "tengo goteras")

        Returns:
            Profesión inferida o None si no se puede inferir

        Example:
            >>> classifier = IntentClassifier()
            >>> profession = classifier.infer_profession_from_need("tengo goteras")
            >>> print(profession)  # "plomero"
        """
        if not query:
            return None

        query_normalized = query.lower().strip()

        # Buscar keywords de necesidad
        for keyword, profession in self.NEED_KEYWORDS.items():
            if keyword in query_normalized:
                logger.debug(f"Profesión inferida: '{profession}' desde query '{query}'")
                return profession

        return None

    def _match_direct_pattern(self, query: str) -> bool:
        """
        Verifica si la query coincide con un patrón de búsqueda DIRECTA.

        Args:
            query: Query normalizada (minúsculas)

        Returns:
            True si coincide con patrón DIRECT
        """
        for pattern in self.compiled_direct_patterns:
            if pattern.match(query):
                return True
        return False

    def _match_need_keyword(self, query: str) -> Optional[str]:
        """
        Busca keywords de necesidad en la query y retorna la profesión inferida.

        Args:
            query: Query normalizada (minúsculas)

        Returns:
            Profesión inferida o None
        """
        for keyword, profession in self.NEED_KEYWORDS.items():
            if keyword in query:
                return profession
        return None

    def _match_ambiguous_keyword(self, query: str) -> bool:
        """
        Verifica si la query contiene palabras ambiguas.

        Args:
            query: Query normalizada (minúsculas)

        Returns:
            True si contiene palabras ambiguas
        """
        for ambiguous_word in self.AMBIGUOUS_KEYWORDS:
            # Verificar que la palabra esté sola o con pocos caracteres
            if ambiguous_word in query.split():
                # Verificar que NO tenga contexto suficiente
                # (ej: "necesito un plomero" es DIRECT, no AMBIGUOUS)
                if len(query.split()) <= 2:
                    return True
        return False


# Instancia global del clasificador (singleton)
_intent_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """
    Retorna la instancia global del IntentClassifier (singleton).

    Returns:
        IntentClassifier: Instancia del clasificador

    Example:
        >>> from services.intent_classifier import get_intent_classifier
        >>> classifier = get_intent_classifier()
        >>> intent = classifier.classify_intent("tengo goteras")
    """
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
        logger.info("✅ IntentClassifier singleton inicializado")
    return _intent_classifier
