"""
Auto Profession Generator - Generación automática de sinónimos para profesiones.

Este módulo genera automáticamente sinónimos cuando se aprueba un nuevo proveedor,
usando un enfoque híbrido de reglas lingüísticas + OpenAI + análisis de componentes.

FEATURE FLAG: USE_AUTO_SYNONYM_GENERATION

Estrategia Anti-Breaking Changes:
- Validación de entradas antes de procesar
- Try/except en todas las operaciones críticas
- No falla si OpenAI no está disponible
- Cache para evitar duplicaciones
- Logs detallados para debugging
"""
import logging
import os
from typing import Any, Dict, List, Optional, Set

from openai import AsyncOpenAI

from services.synonym_generation_rules import SynonymGenerationRules
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class AutoProfessionGenerator:
    """
    Generador automático de sinónimos para profesiones.

    Responsabilidades:
    - Recibir profesión canónica
    - Generar sinónimos usando 3 estrategias (reglas + OpenAI + componentes)
    - Insertar en service_synonyms de forma segura
    - Refrescar cache de DynamicServiceCatalog

    Anti-Breaking:
    - Si OpenAI falla, usa solo reglas
    - Si hay error insertando, loguea pero no rompe
    - Valida duplicados antes de insertar
    """

    def __init__(
        self,
        supabase_client: Any,
        dynamic_service_catalog: Any,
        use_openai: bool = True
    ):
        """
        Inicializa el generador automático de profesiones.

        Args:
            supabase_client: Cliente Supabase para persistir sinónimos
            dynamic_service_catalog: Catálogo dinámico para refrescar cache
            use_openai: Si usar OpenAI para generar sinónimos (default: True)
        """
        self.supabase = supabase_client
        self.dynamic_service_catalog = dynamic_service_catalog
        self.use_openai = use_openai and os.getenv("OPENAI_API_KEY")

        # Inicializar componentes
        self.rules_generator = SynonymGenerationRules()

        # Inicializar OpenAI si está disponible
        self.openai_client: Optional[AsyncOpenAI] = None
        if self.use_openai:
            try:
                self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                logger.info("✅ AutoProfessionGenerator con OpenAI habilitado")
            except Exception as e:
                logger.warning(
                    f"⚠️ No se pudo inicializar OpenAI: {e}. "
                    "Usando solo reglas lingüísticas."
                )
                self.use_openai = False
        else:
            logger.info("✅ AutoProfessionGenerator inicializado (solo reglas)")

        # Cache de profesiones ya procesadas (evitar duplicados)
        self._processed_professions: Set[str] = set()

    async def generate_for_profession(
        self,
        profession: str,
        provider_id: Optional[str] = None,
        city: Optional[str] = None,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera sinónimos para una profesión y los persiste en Supabase.

        Args:
            profession: Profesión canónica
            provider_id: ID del proveedor (opcional, para logging)
            city: Ciudad del proveedor (opcional)
            specialty: Especialidad (opcional)

        Returns:
            Dict con status, profession, synonyms_count
        """
        try:
            # 1. Validar entrada
            if not profession or len(profession.strip()) < 3:
                return {
                    "status": "error",
                    "error": "Profesión inválida (demasiado corta)"
                }

            profession = profession.strip().lower()

            # 2. Verificar si ya fue procesada (cache local)
            if profession in self._processed_professions:
                logger.info(f"ℹ️ Profesión '{profession}' ya procesada en esta sesión")
                return {
                    "status": "already_exists",
                    "profession": profession,
                    "count": 0,
                    "reason": "cached"
                }

            # 3. Verificar si ya existe en Supabase
            existing_count = await self._check_existing_synonyms(profession)
            if existing_count > 0:
                logger.info(
                    f"ℹ️ Profesión '{profession}' ya tiene {existing_count} sinónimos en DB"
                )
                self._processed_professions.add(profession)
                return {
                    "status": "already_exists",
                    "profession": profession,
                    "count": existing_count,
                    "reason": "exists_in_db"
                }

            # 4. Generar sinónimos usando 3 estrategias
            logger.info(f"🔄 Generando sinónimos para '{profession}'...")

            # a) Reglas lingüísticas (determinístico, rápido)
            linguistic_synonyms: Set[str] = set()
            try:
                linguistic_list = self.rules_generator.generate_variations(profession)
                linguistic_synonyms.update(linguistic_list)
                logger.debug(f"  Reglas: {len(linguistic_synonyms)} sinónimos")
            except Exception as e:
                logger.warning(f"⚠️ Error generando variaciones lingüísticas: {e}")

            # b) OpenAI (contextual, más lento)
            openai_synonyms: Set[str] = set()
            if self.use_openai and self.openai_client:
                try:
                    openai_list = await self._generate_with_openai(profession)
                    openai_synonyms.update(openai_list)
                    logger.debug(f"  OpenAI: {len(openai_synonyms)} sinónimos")
                except Exception as e:
                    logger.warning(f"⚠️ Error con OpenAI, usando solo reglas: {e}")

            # c) Análisis de componentes
            component_synonyms: Set[str] = set()
            try:
                component_list = self.rules_generator.generate_component_combinations(profession)
                component_synonyms.update(component_list)
                logger.debug(f"  Componentes: {len(component_synonyms)} sinónimos")
            except Exception as e:
                logger.warning(f"⚠️ Error generando combinaciones: {e}")

            # 5. Unificar y deduplicar
            all_synonyms = list(linguistic_synonyms | openai_synonyms | component_synonyms)

            # Filtrar sinónimos inválidos
            all_synonyms = self._filter_invalid_synonyms(all_synonyms, profession)

            # Remover duplicados con la profesión canónica
            all_synonyms = [s for s in all_synonyms if s != profession]

            if not all_synonyms:
                logger.warning(f"⚠️ No se generaron sinónimos válidos para '{profession}'")
                return {
                    "status": "error",
                    "profession": profession,
                    "error": "no_valid_synonyms"
                }

            logger.info(f"  Total sinónimos generados: {len(all_synonyms)}")

            # 6. Insertar en Supabase
            inserted_count = await self._insert_synonyms(profession, all_synonyms)

            if inserted_count == 0:
                logger.warning(f"⚠️ No se insertaron sinónimos (probablemente duplicados)")
                return {
                    "status": "error",
                    "profession": profession,
                    "error": "no_synonyms_inserted"
                }

            # 7. Refrescar cache de DynamicServiceCatalog
            try:
                await self.dynamic_service_catalog.refresh_cache()
                logger.info("  ✅ Cache de sinónimos refrescado")
            except Exception as e:
                logger.warning(f"⚠️ Error refrescando cache: {e}")

            # 8. Marcar como procesado
            self._processed_professions.add(profession)

            return {
                "status": "created",
                "profession": profession,
                "synonyms_count": inserted_count,
                "provider_id": provider_id,
                "city": city
            }

        except Exception as e:
            logger.error(
                f"❌ Error generando sinónimos para '{profession}': {e}. "
                "No se afectará el funcionamiento del sistema."
            )
            return {
                "status": "error",
                "profession": profession,
                "error": str(e)
            }

    async def _check_existing_synonyms(self, profession: str) -> int:
        """
        Verifica si ya existen sinónimos para una profesión.

        Args:
            profession: Profesión canónica

        Returns:
            Número de sinónimos existentes
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("service_synonyms")
                .select("synonym")
                .eq("canonical_profession", profession)
                .execute(),
                label="service_synonyms.count"
            )

            return len(result.data) if result.data else 0

        except Exception as e:
            logger.warning(f"⚠️ Error verificando sinónimos existentes: {e}")
            return 0

    async def _generate_with_openai(self, profession: str) -> List[str]:
        """
        Genera sinónimos usando OpenAI GPT-3.5.

        Args:
            profession: Profesión canónica

        Returns:
            Lista de sinónimos generados
        """
        try:
            prompt = f"""
Genera 10-15 sinónimos o formas alternativas de decir "{profession}"
en el contexto de servicios profesionales en Ecuador.

Incluye:
- Variaciones regionales (costa, sierra, oriente)
- Términos coloquiales comunes
- Abreviaturas usadas
- Términos en inglés si aplica

IMPORTANTE:
- Responde SOLO una lista separada por comas
- Sin números
- Sin explicaciones
- Solo los sinónimos

Ejemplo de formato:
ingeniero en sistemas, ingeniero de sistemas, especialista en sistemas, técnico en sistemas
"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en servicios profesionales en Ecuador."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()

            # Parsear la respuesta
            synonyms = [s.strip().lower() for s in content.split(",")]
            synonyms = [s for s in synonyms if len(s) > 2]  # Filtrar cortos

            return synonyms

        except Exception as e:
            logger.warning(f"⚠️ Error generando sinónimos con OpenAI: {e}")
            return []

    def _filter_invalid_synonyms(
        self,
        synonyms: List[str],
        profession: str
    ) -> List[str]:
        """
        Filtra sinónimos inválidos.

        Args:
            synonyms: Lista de sinónimos
            profession: Profesión canónica

        Returns:
            Lista filtrada
        """
        filtered: List[str] = []

        for synonym in synonyms:
            # Convertir a minúsculas
            synonym = synonym.strip().lower()

            # Validar longitud
            if len(synonym) < 3 or len(synonym) > 100:
                continue

            # No es solo números
            if synonym.isdigit():
                continue

            # No es igual a la profesión canónica
            if synonym == profession:
                continue

            filtered.append(synonym)

        return filtered

    async def _insert_synonyms(
        self,
        profession: str,
        synonyms: List[str]
    ) -> int:
        """
        Inserta sinónimos en Supabase de forma segura.

        Args:
            profession: Profesión canónica
            synonyms: Lista de sinónimos

        Returns:
            Número de sinónimos insertados
        """
        inserted = 0

        for synonym in synonyms:
            try:
                # Usar ON CONFLICT para evitar duplicados
                await run_supabase(
                    lambda: self.supabase.table("service_synonyms")
                    .insert({
                        "canonical_profession": profession,
                        "synonym": synonym,
                        "active": True
                    })
                    .execute(),
                    label="service_synonyms.insert"
                )
                inserted += 1

            except Exception as e:
                # Probablemente duplicado, continuar
                logger.debug(f"  Sinónimo '{synonym}' ya existe (duplicado)")
                continue

        return inserted

    def get_processed_professions(self) -> Set[str]:
        """
        Retorna el conjunto de profesiones procesadas en esta sesión.

        Returns:
            Set de profesiones procesadas
        """
        return self._processed_professions.copy()
