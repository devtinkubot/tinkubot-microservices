"""
Synonym Generation Rules - Reglas lingüísticas determinísticas para generar sinónimos.

Este módulo contiene reglas lingüísticas que generan variaciones de profesiones
sin usar IA. Es determinístico y rápido.

Incluye:
- Variaciones de preposiciones (de/en/por/para)
- Variaciones de género (masculino/femenino)
- Pluralización
- Términos relacionados
- Traducciones al inglés comunes
"""
import logging
import re
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)


# Preposiciones alternas en español
PREPOSITIONS = ["de", "en", "por", "para", "con"]

# Términos de nivel/especialidad comunes
LEVEL_PREFIXES = {
    "junior": ["asistente", "ayudante", "aprendiz", "junior"],
    "senior": ["senior", "experto", "principal", "lead"],
    "technical": ["técnico", "tecnica", "operador", "operadora"],
}

# Traducciones comunes al inglés
ENGLISH_TRANSLATIONS = {
    "ingeniero": "engineer",
    "desarrollador": "developer",
    "diseñador": "designer",
    "arquitecto": "architect",
    "consultor": "consultant",
    "analista": "analyst",
    "gerente": "manager",
    "director": "director",
    "administrador": "administrator",
    "profesor": "teacher",
    "doctor": "doctor",
    "enfermero": "nurse",
    "abogado": "lawyer",
    "contador": "accountant",
}


class SynonymGenerationRules:
    """
    Generador de sinónimos basado en reglas lingüísticas.

    Estrategia:
    1. Variaciones de preposiciones
    2. Variaciones de género
    3. Pluralización
    4. Términos relacionados
    5. Traducciones al inglés
    """

    def __init__(self):
        """Inicializa el generador de reglas."""
        logger.info("✅ SynonymGenerationRules inicializado")

    def generate_variations(self, profession: str) -> List[str]:
        """
        Genera variaciones de una profesión usando reglas lingüísticas.

        Args:
            profession: Profesión canónica (ej: "ingeniero de sistemas")

        Returns:
            Lista de sinónimos generados
        """
        variations: Set[str] = set()

        # 1. Incluir la profesión original
        variations.add(profession)

        # 2. Variaciones de preposiciones
        variations.update(self._vary_prepositions(profession))

        # 3. Variaciones de género
        variations.update(self._vary_gender(profession))

        # 4. Pluralización
        variations.update(self._pluralize(profession))

        # 5. Sin tilde (variaciones comunes en texting)
        variations.update(self._remove_accents(profession))

        # 6. Términos relacionados
        variations.update(self._generate_related_terms(profession))

        # 7. Traducciones al inglés
        variations.update(self._translate_to_english(profession))

        # 8. Abreviaturas comunes
        variations.update(self._generate_abbreviations(profession))

        return list(variations)

    def _vary_prepositions(self, profession: str) -> Set[str]:
        """
        Genera variaciones alternando preposiciones.

        Ejemplo: "ingeniero de sistemas" → "ingeniero en sistemas"
        """
        variations: Set[str] = set()

        # Buscar patrones como "X de Y" o "X en Y"
        for prep_in in PREPOSITIONS:
            for prep_out in PREPOSITIONS:
                if prep_in == prep_out:
                    continue

                # Patrón: "X {prep_in} Y"
                pattern = rf"(\w+)\s+{re.escape(prep_in)}\s+(\w+)"

                match = re.search(pattern, profession, re.IGNORECASE)
                if match:
                    base = match.group(1)
                    suffix = match.group(2)
                    variation = f"{base} {prep_out} {suffix}"
                    variations.add(variation.lower())

        return variations

    def _vary_gender(self, profession: str) -> Set[str]:
        """
        Genera variaciones de género (masculino/femenino).

        Ejemplo: "ingeniero" → "ingeniera"
        """
        variations: Set[str] = set()

        # Sufijos comunes de género
        gender_rules: List[Tuple[str, str]] = [
            ("o", "a"),  # ingeniero → ingeniera
            ("or", "ora"),  # doctor → doctora
            ("er", "era"),  # panader(o/a) → panadera
        ]

        for masc_suffix, fem_suffix in gender_rules:
            if profession.endswith(masc_suffix):
                # Variación femenina
                feminine = profession[:-len(masc_suffix)] + fem_suffix
                variations.add(feminine)

        return variations

    def _pluralize(self, profession: str) -> Set[str]:
        """
        Genera forma plural.

        Ejemplo: "ingeniero" → "ingenieros"
        """
        variations: Set[str] = set()

        # Reglas de pluralización en español
        if profession.endswith("ión"):
            #ción → ces
            plural = profession[:-3] + "ones"
            variations.add(plural)
        elif profession.endswith("z"):
            #z → ces
            plural = profession[:-1] + "ces"
            variations.add(plural)
        elif profession.endswith("l") or profession.endswith("n") or profession.endswith("r"):
            # consonante → +es
            plural = profession + "es"
            variations.add(plural)
        elif not profession.endswith("s"):
            # vocal → +s
            plural = profession + "s"
            variations.add(plural)

        return variations

    def _remove_accents(self, profession: str) -> Set[str]:
        """
        Genera variaciones sin tilde (común en texting).

        Ejemplo: "ingeniería" → "ingenieria"
        """
        variations: Set[str] = set()

        # Reemplazos de tildes
        accent_map = {
            'á': 'a',
            'é': 'e',
            'í': 'i',
            'ó': 'o',
            'ú': 'u',
            'Á': 'A',
            'É': 'E',
            'Í': 'I',
            'Ó': 'O',
            'Ú': 'U',
        }

        no_accent = profession
        for accented, unaccented in accent_map.items():
            no_accent = no_accent.replace(accented, unaccented)

        if no_accent != profession:
            variations.add(no_accent)

        return variations

    def _generate_related_terms(self, profession: str) -> Set[str]:
        """
        Genera términos relacionados basados en la profesión.

        Ejemplo: "ingeniero de sistemas" → "técnico en sistemas"
        """
        variations: Set[str] = set()

        # Extraer componentes
        words = profession.split()

        if len(words) >= 2:
            # Para "X de Y", generar variaciones con diferentes prefijos
            for level, prefixes in LEVEL_PREFIXES.items():
                for prefix in prefixes:
                    if "de" in profession or "en" in profession:
                        # "ingeniero de sistemas" → "técnico en sistemas"
                        parts = profession.split()
                        if len(parts) >= 3:
                            # Reemplazar el primer término
                            parts[0] = prefix
                            variation = " ".join(parts)
                            variations.add(variation)

        return variations

    def _translate_to_english(self, profession: str) -> Set[str]:
        """
        Genera traducción al inglés si existe.

        Ejemplo: "ingeniero" → "engineer"
        """
        variations: Set[str] = set()

        for spanish, english in ENGLISH_TRANSLATIONS.items():
            if spanish.lower() in profession.lower():
                # Reemplazar término en español por inglés
                translated = profession.replace(
                    spanish,
                    english,
                    1  # Solo primera ocurrencia
                )
                variations.add(translated)

        return variations

    def _generate_abbreviations(self, profession: str) -> Set[str]:
        """
        Genera abreviaturas comunes.

        Ejemplo: "ingeniero de sistemas" → "ing. de sistemas"
        """
        variations: Set[str] = set()

        # Abreviaturas comunes
        abbreviations = {
            "ingeniero": "ing",
            "doctor": "dr",
            "doctora": "dra",
            "profesor": "prof",
            "profesora": "profa",
            "licenciado": "lic",
            "licenciada": "lica",
            "administrador": "admin",
            "gerente": "ger",
        }

        for full, abbr in abbreviations.items():
            if full.lower() in profession.lower():
                abbreviated = profession.replace(full, abbr, 1)
                variations.add(abbreviated)

        return variations

    def generate_component_combinations(self, profession: str) -> List[str]:
        """
        Genera combinaciones basadas en los componentes de la profesión.

        Ejemplo: "ingeniero de sistemas" → ["especialista en sistemas", "técnico de sistemas"]

        Args:
            profession: Profesión canónica

        Returns:
            Lista de combinaciones
        """
        combinations: List[str] = []

        # Extraer palabras clave
        words = profession.split()

        if len(words) >= 2:
            # Para profesiones compuestas de 2+ palabras
            for i, word in enumerate(words):
                if word in ["de", "en", "por", "para", "con"]:
                    # Encontrar la palabra clave después de la preposición
                    if i + 1 < len(words):
                        keyword = words[i + 1]

                        # Generar combinaciones con diferentes prefijos
                        combinations.extend([
                            f"especialista {word} {keyword}",
                            f"técnico {word} {keyword}",
                            f"experto {word} {keyword}",
                            f"profesional {word} {keyword}",
                        ])

        return combinations
