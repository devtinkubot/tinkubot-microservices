"""
Servicio de búsqueda simplificado según flujo estricto especificado.
Sin cachés, sin fallbacks, sin optimizaciones adicionales.
"""

import os
import json
import unicodedata
from typing import List, Dict, Optional
from openai import OpenAI
from supabase import Client

# Configuración
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Lista hardcoded de ciudades ecuatorianas
ECUADORIAN_CITIES = [
    "quito", "guayaquil", "cuenca", "ambato", "riobamba",
    "manta", "portoviejo", "loja", "esmeraldas", "sindo domingo",
    "machala", "duran", "ibarra", "babahoyo", "quevedo",
    "milagro", "cayambe", "otavalo", "tulcan", "el oro",
    "latacunga", "ambato", "esmeraldas", "santa elena"
]


class SimpleSearchService:
    """Servicio de búsqueda con flujo estricto."""

    def __init__(self):
        """Inicializar con clientes singleton."""
        self._openai_client = None
        self._supabase_client = None

    @property
    def openai_client(self) -> OpenAI:
        """Lazy init de OpenAI client."""
        if self._openai_client is None:
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self._openai_client = OpenAI(api_key=OPENAI_API_KEY)
        return self._openai_client

    @property
    def supabase(self) -> Client:
        """Obtiene el singleton de Supabase del sistema (no crea uno nuevo)."""
        from utils.supabase_client import get_supabase_client

        client = get_supabase_client()
        if client is None:
            raise ValueError("Supabase client singleton no está inicializado")
        return client

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normaliza texto para búsqueda.
        - Convierte a minúsculas
        - Elimina acentos usando NFD
        - Elimina preposiciones cuando están ENTRE palabras (no al inicio/final)
        - Elimina espacios múltiples y recorta
        """
        if not text:
            return ""

        # Paso 1: Minúsculas
        text = text.lower()

        # Paso 2: Eliminar acentos (NFD normalization + remove diacritics)
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

        # Paso 3: Eliminar preposiciones cuando están ENTRE palabras
        prepositions = ["de", "en", "lo", "la", "los", "las", "el"]
        words = text.split()

        # Reconstruir texto eliminando preposiciones que no están al inicio o final
        if len(words) > 2:  # Solo si hay más de 2 palabras
            filtered_words = []
            for i, word in enumerate(words):
                # Mantener palabra si:
                # - Es la primera palabra
                # - Es la última palabra
                # - No es una preposición
                if i == 0 or i == len(words) - 1 or word not in prepositions:
                    filtered_words.append(word)
            text = ' '.join(filtered_words)

        # Paso 4: Eliminar espacios múltiples y recortar
        text = ' '.join(text.split())

        return text

    @staticmethod
    def clean_message(message: str) -> str:
        """Paso 1: Recepción y Lógica de limpieza."""
        return SimpleSearchService.normalize_text(message)

    @staticmethod
    def extract_city(message: str) -> Optional[str]:
        """Extracción básica de ciudad de lista hardcoded."""
        message_lower = message.lower()
        for city in ECUADORIAN_CITIES:
            if city in message_lower:
                return city
        return None

    def call_ai(self, message: str) -> Dict:
        """Paso 2: Generación con IA (única llamada)."""
        prompt = f"""Analiza el siguiente mensaje de búsqueda de proveedores en Ecuador y responde EXCLUSIVAMENTE en JSON válido sin formato markdown.

Mensaje: "{message}"

Tu respuesta debe ser un JSON con esta estructura exacta:
{{
  "type": "profesion" o "necesidad",
  "term": "término principal extraído (ej: plomero, electricista)",
  "synonyms": ["sinónimo1", "sinónimo2", "sinónimo3"]  (solo si type=profesion)
  "professions": ["profesion1", "profesion2", "profesion3"] (sino si type=necesidad),
  "keywords": ["keyword1", "keyword2"] (solo si type=necesidad, 2-4 palabras clave normalizadas)
}}

Reglas:
- Si el usuario menciona directamente una profesión (plomero, doctor, etc.), type="profesion"
- Si el usuario describe un problema/síntoma (goteras, dolor, etc.), type="necesidad"
- Genera 3+ sinónimos o profesiones relacionadas
- keywords solo para necesidad, 2-4 términos normalizados (ej: "fuga agua", "reparacion tuberia")
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty content")
        return json.loads(content)

    @staticmethod
    def prepare_search_terms(ai_result: Dict) -> List[str]:
        """
        Paso 3: Preparación de Términos de Búsqueda.
        Aplica normalización a todos los términos y elimina duplicados.
        """
        # Recopilar todos los términos
        terms = [ai_result["term"]]

        if ai_result["type"] == "profesion":
            terms.extend(ai_result.get("synonyms", []))
        else:  # necesidad
            terms.extend(ai_result.get("professions", []))
            terms.extend(ai_result.get("keywords", []))

        # Aplicar normalización a cada término
        normalized_terms = [SimpleSearchService.normalize_text(term) for term in terms]

        # Eliminar duplicados manteniendo orden (usando dict desde Python 3.7+)
        unique_terms = list(dict.fromkeys(normalized_terms))

        return unique_terms

    def search_supabase(self, terms: List[str], city: Optional[str]) -> List[Dict]:
        """Paso 4: Búsqueda Directa en Supabase."""
        # Construir filtro OR múltiple
        or_conditions = []
        for term in terms:
            or_conditions.append(f"profession.ilike.%{term}%")
            or_conditions.append(f"services.ilike.%{term}%")

        # Query base
        query = self.supabase.table("providers").select("*")

        # Filtro verified
        query = query.eq("verified", True)

        # Filtro ciudad si detectada
        if city:
            query = query.ilike("city", f"%{city}%")

        # Aplicar OR conditions
        if or_conditions:
            query = query.or_(",".join(or_conditions))

        # Paso 5: Orden por rating DESC
        query = query.order("rating", desc=True)

        # Ejecutar query
        result = query.execute()
        data = result.data
        if not data:
            return []
        # Type narrowing: ensure all items are dicts
        return [item for item in data if isinstance(item, dict)]

    @staticmethod
    def check_availability(providers: List[Dict]) -> List[Dict]:
        """Paso 5: Filtro de disponibilidad (placeholder simple)."""
        # Placeholder simple sin lógica compleja
        # En implementación real: verificar disponibilidad via MQTT
        return providers

    @staticmethod
    def format_response(providers: List[Dict]) -> str:
        """Paso 6: Respuesta formateada."""
        if not providers:
            return "No encontré proveedores disponibles con esos criterios. ¿Puedes ser más específico?"

        count = len(providers)
        response = f"Encontré {count} {'proveedor' if count == 1 else 'proveedores'}:\n\n"

        for i, provider in enumerate(providers[:10], 1):  # Máximo 10
            response += f"{i}. {provider.get('name', 'N/A')} - {provider.get('profession', 'A/V')}\n"
            response += f"   📍 {provider.get('city', 'N/A')}\n"
            response += f"   ⭐ {provider.get('rating', 0)}\n"
            if provider.get('services'):
                response += f"   🔧 Servicios: {provider['services']}\n"
            response += "\n"

        if count > 10:
            response += f"\n... y {count - 10} más."

        return response

    def search(self, message: str) -> List[Dict]:
        """Flujo principal completo - devuelve proveedores crudos."""
        # Paso 1: Limpieza
        cleaned = self.clean_message(message)

        # Paso 1: Extracción de ciudad
        city = self.extract_city(cleaned)

        # Paso 2: Generación IA
        ai_result = self.call_ai(cleaned)

        # Paso 3: Preparar términos
        terms = self.prepare_search_terms(ai_result)

        # Paso 4: Búsqueda Supabase (usando singleton)
        providers = self.search_supabase(terms, city)

        # Paso 5: Disponibilidad
        available_providers = self.check_availability(providers)

        # Devolver proveedores crudos - el flujo original se encarga de formatear
        return available_providers

    def search_and_format(self, message: str) -> str:
        """Versión con formateo incluido - para endpoints HTTP directos."""
        providers = self.search(message)
        return self.format_response(providers)
