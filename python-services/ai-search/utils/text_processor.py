"""
Módulo centralizado de normalización y tokenización de texto
para búsquedas eficientes en Search Service
"""

import logging
import re
import unicodedata
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Stop words en español que podemos ignorar en búsquedas
STOP_WORDS = {
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "de",
    "del",
    "en",
    "con",
    "por",
    "para",
    "y",
    "o",
    "pero",
    "mas",
    "más",
    "como",
    "cuando",
    "donde",
    "que",
    "qué",
    "cual",
    "cuál",
    "quien",
    "quién",
    "mi",
    "tu",
    "su",
    "nuestro",
    "al",
    "a",
    "se",
    "sus",
    "mis",
    "tus",
    "este",
    "esta",
    "estos",
    "estas",
    "necesito",
    "busco",
    "buscamos",
    "requiero",
    "quiero",
    "deseo",
    "urgente",
    "ahora",
    "hoy",
    "mañana",
    "tarde",
    "noche",
    "favor",
    "por favor",
}

# Palabras clave de servicio con alta prioridad
SERVICE_KEYWORDS = {
    "medico",
    "doctor",
    "doctora",
    "enfermera",
    "enfermero",
    "abogado",
    "abogada",
    "contador",
    "contadora",
    "ingeniero",
    "ingeniera",
    "arquitecto",
    "arquitecta",
    "diseñador",
    "diseñadora",
    "profesor",
    "profesora",
    "plomero",
    "electricista",
    "mecanico",
    "pintor",
    "albañil",
    "gasfitero",
    "cerrajero",
    "veterinario",
    "chef",
    "mesero",
    "bartender",
    "carpintero",
    "jardinero",
    "marketing",
    "publicidad",
    "diseño",
    "consultor",
    "desarrollador",
    "programador",
    "software",
    "web",
    "legal",
    "finanzas",
    "contable",
    "fontanero",
    # Servicios de belleza y cuidado personal
    "esteticista",
    "cosmetologa",
    "cosmetologo",
    "belleza",
    "facial",
    "piel",
    "cuidado",
    "limpieza",
    "tratamiento",
    "tratamientos",
    "maquillaje",
    "makeup",
    "cejas",
    "labios",
    "micropigmentacion",
    "tatuaje",
    "depilacion",
    "spa",
    "masaje",
    "masajista",
    "uñas",
    "manicura",
    "pedicura",
    "barber",
    "barberia",
    "cabello",
    "cortar",
    "peinar",
    "color",
    "tinte",
}

# Sinónimos de servicios (extraído del código existente)
SERVICE_SYNONYMS = {
    "plomero": {"plomero", "plomeria", "plomería"},
    "electricista": {"electricista", "electricistas"},
    "médico": {"médico", "medico", "doctor", "doctora"},
    "mecánico": {
        "mecanico",
        "mecánico",
        "mecanicos",
        "mecanica automotriz",
        "taller mecanico",
    },
    "pintor": {"pintor", "pintura", "pintores"},
    "albañil": {"albañil", "albanil", "maestro de obra"},
    "gasfitero": {"gasfitero", "gasfiteria", "fontanero"},
    "cerrajero": {"cerrajero", "cerrajeria"},
    "veterinario": {"veterinario", "veterinaria"},
    "chef": {"chef", "cocinero", "cocinera"},
    "mesero": {"mesero", "mesera", "camarero", "camarera"},
    "profesor": {"profesor", "profesora", "maestro", "maestra"},
    "bartender": {"bartender", "barman"},
    "carpintero": {"carpintero", "carpinteria"},
    "jardinero": {"jardinero", "jardineria"},
    "marketing": {
        "marketing",
        "marketing digital",
        "mercadotecnia",
        "publicidad",
        "publicista",
        "agente de publicidad",
        "campanas de marketing",
        "campanas publicitarias",
    },
    "diseñador gráfico": {
        "diseño grafico",
        "diseno grafico",
        "diseñador grafico",
        "designer grafico",
        "graphic designer",
        "diseñador",
    },
    "consultor": {
        "consultor",
        "consultoria",
        "consultoría",
        "asesor",
        "asesoria",
        "asesoría",
        "consultor de negocios",
    },
    "desarrollador": {
        "desarrollador",
        "programador",
        "developer",
        "desarrollo web",
        "software developer",
        "ingeniero de software",
    },
    "contador": {
        "contador",
        "contadora",
        "contable",
        "contabilidad",
        "finanzas",
    },
    "abogado": {
        "abogado",
        "abogada",
        "legal",
        "asesoria legal",
        "asesoría legal",
        "servicios legales",
    },
    # Servicios de belleza y cuidado personal
    "esteticista": {
        "esteticista",
        "cosmetologa",
        "cosmetologo",
        "belleza",
        "cuidado facial",
        "facial",
        "tratamientos faciales",
        "limpieza facial",
        "cuidado de piel",
        "cuidados piel",
        "tratamientos de belleza",
        "skin care",
        "skincare",
    },
    "maquilladora": {
        "maquilladora",
        "maquillador",
        "maquillaje",
        "makeup artist",
        "makeup",
        "maquillaje profesional",
        "maquillaje social",
        "maquillaje artistico",
        "maquillaje artistico",
    },
    "micropigmentadora": {
        "micropigmentadora",
        "micropigmentador",
        "micropigmentacion",
        "maquillaje permanente",
        "maquillaje semipermanente",
        "tatuaje cosmetico",
        "cejas permanentes",
        "labios permanentes",
        "delineador permanente",
        "cejas",
        "labios",
        "ojos",
    },
    "manicurista": {
        "manicurista",
        "uñas",
        "manicura",
        "pedicura",
        "uñas acrilicas",
        "uñas gel",
        "esculpidas",
        "nail artist",
        "arte en uñas",
    },
    "masajista": {
        "masajista",
        "masaje",
        "masajes",
        "masajes terapeuticos",
        "masajes relajantes",
        "masaje deportivo",
        "terapia fisica",
        "rehabilitacion",
        "spa",
        "wellness",
    },
    "barber": {
        "barber",
        "barbero",
        "barberia",
        "corte de cabello",
        "cortar pelo",
        "peinar",
        "estilista",
        "peluquero",
        "cabello",
        "pelo",
        "coloracion",
        "tinte",
        "decoloracion",
    },
    "depiladora": {
        "depiladora",
        "depilacion",
        "depilacion laser",
        "cera",
        "cera caliente",
        "depilacion con cera",
        "cuerpo completo",
        "piernas",
        "brazos",
        "axilas",
        "zona intima",
    },
}

# Ciudades de Ecuador (versión normalizada)
ECUADOR_CITIES_NORMALIZED = {
    "quito": "Quito",
    "guayaquil": "Guayaquil",
    "cuenca": "Cuenca",
    "santo domingo": "Santo Domingo",
    "santo domingo de los tsachilas": "Santo Domingo",
    "manta": "Manta",
    "portoviejo": "Portoviejo",
    "machala": "Machala",
    "duran": "Durán",
    "durán": "Durán",
    "loja": "Loja",
    "ambato": "Ambato",
    "riobamba": "Riobamba",
    "esmeraldas": "Esmeraldas",
    "quevedo": "Quevedo",
    "babahoyo": "Babahoyo",
    "baba hoyo": "Babahoyo",
    "milagro": "Milagro",
    "ibarra": "Ibarra",
    "tulcan": "Tulcán",
    "tulcán": "Tulcán",
    "latacunga": "Latacunga",
    "salinas": "Salinas",
}


class TextProcessor:
    """Procesador de texto especializado en búsqueda de servicios"""

    @staticmethod
    def normalize_text_for_search(text: Optional[str]) -> str:
        """
        Normaliza texto para búsqueda:
        - Convierte a minúsculas
        - Elimina acentos
        - Elimina caracteres especiales excepto espacios
        - Unifica espacios múltiples
        """
        if not text:
            return ""

        # Convertir a minúsculas
        text = text.lower().strip()

        # Eliminar acentos y caracteres diacríticos
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")

        # Limpiar caracteres especiales (mantener solo letras, números y espacios)
        text = re.sub(r"[^a-z0-9\s]", " ", text)

        # Unificar espacios múltiples
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def tokenize_text(text: Optional[str], remove_stop_words: bool = True) -> List[str]:
        """
        Convierte texto en lista de tokens normalizados
        """
        if not text:
            return []

        # Normalizar texto
        normalized = TextProcessor.normalize_text_for_search(text)

        # Dividir en tokens
        tokens = normalized.split()

        # Opcionalmente remover stop words
        if remove_stop_words:
            tokens = [token for token in tokens if token not in STOP_WORDS]

        # Remover duplicados manteniendo orden
        seen = set()
        unique_tokens = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)

        return unique_tokens

    @staticmethod
    def extract_service_tokens(tokens: List[str]) -> List[str]:
        """
        Extrae tokens que corresponden a servicios/profesiones
        """
        service_tokens = []

        # Primero buscar coincidencias directas
        for token in tokens:
            if token in SERVICE_KEYWORDS:
                service_tokens.append(token)

        # Luego buscar en sinónimos
        for canonical, synonyms in SERVICE_SYNONYMS.items():
            for synonym in synonyms:
                normalized_synonym = TextProcessor.normalize_text_for_search(synonym)
                if normalized_synonym in tokens:
                    service_tokens.append(normalized_synonym)

        return list(set(service_tokens))  # Remover duplicados

    @staticmethod
    def extract_city_token(tokens: List[str]) -> Optional[str]:
        """
        Extrae y normaliza token de ciudad si existe
        """
        for token in tokens:
            if token in ECUADOR_CITIES_NORMALIZED:
                return ECUADOR_CITIES_NORMALIZED[token]

        # Buscar combinaciones de 2 palabras para ciudades compuestas
        for i in range(len(tokens) - 1):
            two_word_city = f"{tokens[i]} {tokens[i+1]}"
            if two_word_city in ECUADOR_CITIES_NORMALIZED:
                return ECUADOR_CITIES_NORMALIZED[two_word_city]

        return None

    @staticmethod
    def calculate_relevance_score(
        query_tokens: List[str], provider_tokens: List[str]
    ) -> float:
        """
        Calcula puntaje de relevancia entre consulta y proveedor
        """
        if not query_tokens or not provider_tokens:
            return 0.0

        query_set = set(query_tokens)
        provider_set = set(provider_tokens)

        # Tokens coincidentes
        intersection = query_set.intersection(provider_set)

        # Tokens de servicio tienen más peso
        service_tokens = TextProcessor.extract_service_tokens(query_tokens)
        service_matches = len(intersection.intersection(service_tokens))

        # Calcular puntaje base
        base_score = len(intersection) / len(query_set)

        # Bono por tokens de servicio
        service_bonus = (service_matches * 0.2) if service_matches else 0

        # Bono por coincidencia exacta
        exact_match_bonus = 0.3 if len(intersection) == len(query_set) else 0

        total_score = min(1.0, base_score + service_bonus + exact_match_bonus)

        return total_score

    @staticmethod
    def normalize_profession_name(profession: str) -> str:
        """
        Normaliza nombre de profesión para almacenamiento consistente
        """
        if not profession:
            return ""

        normalized = TextProcessor.normalize_text_for_search(profession)

        # Buscar en sinónimos normalizados
        for canonical, synonyms in SERVICE_SYNONYMS.items():
            for synonym in synonyms:
                if TextProcessor.normalize_text_for_search(synonym) == normalized:
                    return canonical

        return normalized

    @staticmethod
    def normalize_city_name(city: str) -> str:
        """
        Normaliza nombre de ciudad para almacenamiento consistente
        """
        if not city:
            return ""

        normalized = TextProcessor.normalize_text_for_search(city)
        return ECUADOR_CITIES_NORMALIZED.get(normalized, city.title())

    @staticmethod
    def create_search_index(text: Optional[str]) -> List[str]:
        """
        Crea índice de búsqueda completo para un texto
        Incluye tokens individuales y combinaciones relevantes
        """
        if not text:
            return []

        # Tokens principales
        tokens = TextProcessor.tokenize_text(text, remove_stop_words=True)

        # Agregar tokens sin remover stop words para búsqueda exacta
        all_tokens = TextProcessor.tokenize_text(text, remove_stop_words=False)

        # Combinar y eliminar duplicados
        combined_tokens = list(set(tokens + all_tokens))

        # Agregar tokens de servicio normalizados
        service_tokens = TextProcessor.extract_service_tokens(combined_tokens)
        combined_tokens.extend(service_tokens)

        # Remover duplicados finales y ordenar
        unique_tokens = sorted(list(set(combined_tokens)))

        return unique_tokens

    @staticmethod
    def analyze_query(text: str) -> dict:
        """
        Analiza una consulta y extrae información estructurada
        """
        tokens = TextProcessor.tokenize_text(text, remove_stop_words=True)
        service_tokens = TextProcessor.extract_service_tokens(tokens)
        city = TextProcessor.extract_city_token(tokens)

        # Detectar urgencia
        urgency_keywords = {"urgente", "ya", "ahora", "inmediato", "rápido", "pronto"}
        has_urgency = any(keyword in tokens for keyword in urgency_keywords)

        return {
            "original_text": text,
            "normalized_text": TextProcessor.normalize_text_for_search(text),
            "tokens": tokens,
            "service_tokens": service_tokens,
            "city": city,
            "has_urgency": has_urgency,
            "token_count": len(tokens),
            "has_clear_intent": len(service_tokens) > 0,
        }


# Funciones de conveniencia para compatibilidad
def normalize_text_for_search(text: Optional[str]) -> str:
    return TextProcessor.normalize_text_for_search(text)


def tokenize_text(text: Optional[str], remove_stop_words: bool = True) -> List[str]:
    return TextProcessor.tokenize_text(text, remove_stop_words)


def extract_service_tokens(tokens: List[str]) -> List[str]:
    return TextProcessor.extract_service_tokens(tokens)


def extract_city_token(tokens: List[str]) -> Optional[str]:
    return TextProcessor.extract_city_token(tokens)


def calculate_relevance_score(
    query_tokens: List[str], provider_tokens: List[str]
) -> float:
    return TextProcessor.calculate_relevance_score(query_tokens, provider_tokens)


def normalize_profession_name(profession: str) -> str:
    return TextProcessor.normalize_profession_name(profession)


def normalize_city_name(city: str) -> str:
    return TextProcessor.normalize_city_name(city)


def create_search_index(text: Optional[str]) -> List[str]:
    return TextProcessor.create_search_index(text)


def analyze_query(text: str) -> dict:
    return TextProcessor.analyze_query(text)
