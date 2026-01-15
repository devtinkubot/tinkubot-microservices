"""
Synonym Learner Service - Aprendizaje Automático de Sinónimos.

Este módulo implementa aprendizaje automático de sinónimos a partir de búsquedas
exitosas. Los sinónimos aprendidos se agregan AUTOMÁTICAMENTE a service_synonyms.

ESTRATEGIA AUTOMÁTICA:
- Feature flag: USE_SYNONYM_LEARNING (default: False)
- Agrega automáticamente a service_synonyms
- NO requiere aprobación manual
- Mantener tracking en learned_synonyms para auditoría

LÓGICA DE APRENDIZAJE:
1. Una búsqueda encuentra resultados (num_results > 0)
2. El query NO existe en service_synonyms
3. El query es diferente a la profesión canónica
4. Se calcula confidence_score
5. Se inserta AUTOMÁTICAMENTE en service_synonyms (status='approved')
6. Se mantiene registro en learned_synonyms para auditoría

Author: Claude Sonnet 4.5
Created: 2026-01-15
Updated: 2026-01-15 - Automatizado (sin aprobación manual)
"""

import logging
from typing import Any, Dict, Optional
from decimal import Decimal

from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class SynonymLearner:
    """
    Sistema de aprendizaje automático de sinónimos.

    Responsabilidades:
    - Observar búsquedas exitosas
    - Extraer potenciales nuevos sinónimos
    - Calcular confidence score
    - Insertar AUTOMÁTICAMENTE en service_synonyms
    - Mantener registro en learned_synonyms para auditoría

    AUTOMÁTICO: No requiere aprobación manual.
    """

    def __init__(self, supabase_client):
        """Inicializa el sistema de aprendizaje.

        Args:
            supabase_client: Cliente Supabase para guardar aprendizajes
        """
        self.supabase = supabase_client
        logger.info("✅ SynonymLearner inicializado")

    async def learn_from_search(
        self,
        query: str,
        matched_profession: str,
        num_results: int,
        city: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Aprende un sinónimo potencial de una búsqueda exitosa.

        Args:
            query: Query original del usuario
            matched_profession: Profesión que hizo match
            num_results: Número de resultados encontrados
            city: Ciudad de búsqueda (opcional)
            context: Contexto adicional (expansion_method, etc.)

        Returns:
            Dict con el aprendizaje creado o None si no se aprendió nada

        Example:
            >>> learner = SynonymLearner(supabase)
            >>> result = await learner.learn_from_search(
            ...     query="community manager",
            ...     matched_profession="marketing",
            ...     num_results=5
            ... )
        """
        from core.feature_flags import USE_SYNONYM_LEARNING

        # Feature flag: desactivado = no aprender
        if not USE_SYNONYM_LEARNING:
            logger.debug("⚠️ USE_SYNONYM_LEARNING=False, skipping learning")
            return None

        # Validaciones previas
        if not self._should_learn(query, matched_profession, num_results):
            logger.debug(f"Query '{query}' no cumple criterios de aprendizaje")
            return None

        try:
            # Normalizar query
            normalized_query = self._normalize_query(query)
            if not normalized_query:
                return None

            # Verificar si ya existe en learned_synonyms
            existing = await self._get_existing_learned(
                matched_profession,
                normalized_query
            )

            if existing:
                # Actualizar match_count y confidence
                return await self._update_existing_learned(existing)

            # Calcular confidence score inicial
            confidence = self._calculate_confidence_score(
                query=query,
                matched_profession=matched_profession,
                num_results=num_results,
                context=context
            )

            # Insertar AUTOMÁTICAMENTE en service_synonyms
            # Primero verificar si ya existe en service_synonyms
            existing_in_service = await self._check_existing_in_service_synonyms(
                matched_profession,
                normalized_query
            )

            if existing_in_service:
                # Ya existe, solo actualizar match_count en learned_synonyms
                logger.debug(f"Sinónimo '{normalized_query}' ya existe en service_synonyms")
                return None

            # Insertar en service_synonyms AUTOMÁTICAMENTE
            inserted = await self._insert_to_service_synonyms(
                canonical_profession=matched_profession,
                synonym=normalized_query
            )

            if inserted:
                # Guardar registro en learned_synonyms para auditoría (status='approved')
                learned = await self._insert_learned_synonym_audit(
                    canonical_profession=matched_profession,
                    learned_synonym=normalized_query,
                    source_query=query,
                    confidence_score=confidence
                )

                # Refrescar cache de service_synonyms
                from services.dynamic_service_catalog import dynamic_service_catalog
                if dynamic_service_catalog:
                    await dynamic_service_catalog.refresh_cache()

                logger.info(
                    f"🧠 [LEARNING] Nuevo sinónimo aprendido AUTOMÁTICAMENTE: '{normalized_query}' → '{matched_profession}' "
                    f"(confidence: {confidence:.2f}, results: {num_results})"
                )

                return learned

            return None

        except Exception as e:
            logger.error(f"❌ Error en learn_from_search: {e}")
            return None

    def _should_learn(
        self,
        query: str,
        matched_profession: str,
        num_results: int
    ) -> bool:
        """
        Determina si una búsqueda cumple criterios para aprendizaje.

        Criterios:
        1. Debe tener al menos 1 resultado
        2. El query debe ser diferente a la profesión canónica
        3. El query no debe ser un número puro
        4. El query debe tener longitud mínima (3 caracteres)
        """
        # Criterio 1: Debe tener resultados
        if num_results == 0:
            logger.debug(f"No learning: sin resultados")
            return False

        # Criterio 2: Query diferente a profesión canónica
        if query.lower().strip() == matched_profession.lower().strip():
            logger.debug(f"No learning: query igual a profesión canónica")
            return False

        # Criterio 3: No ser un número puro
        if query.strip().isdigit():
            logger.debug(f"No learning: query es número puro")
            return False

        # Criterio 4: Longitud mínima
        if len(query.strip()) < 3:
            logger.debug(f"No learning: query muy corto")
            return False

        # Criterio 5: Query no debe contener solo stopwords
        if self._is_stopword_only(query):
            logger.debug(f"No learning: query solo contiene stopwords")
            return False

        return True

    def _normalize_query(self, query: str) -> Optional[str]:
        """Normaliza el query para almacenamiento."""
        if not query:
            return None

        # Minúsculas, trim, sin espacios extras
        normalized = query.lower().strip()

        # Limitar longitud máxima (200 caracteres como en la DB)
        if len(normalized) > 200:
            normalized = normalized[:200]

        return normalized

    def _is_stopword_only(self, query: str) -> bool:
        """Verifica si el query solo contiene palabras vacías."""
        stopwords = {
            'el', 'la', 'de', 'en', 'un', 'una', 'por', 'para',
            'con', 'sin', 'sobre', 'tras', 'hasta', 'desde',
            'que', 'qual', 'como', 'donde', 'cuando', 'quien'
        }

        query_lower = query.lower().strip()
        words = query_lower.split()

        # Si todas las palabras son stopwords
        return all(word in stopwords for word in words)

    async def _get_existing_learned(
        self,
        canonical_profession: str,
        learned_synonym: str
    ) -> Optional[Dict[str, Any]]:
        """Busca si ya existe un aprendizaje previo."""
        try:
            result = await run_supabase(
                lambda: self.supabase.table("learned_synonyms")
                .select("*")
                .eq("canonical_profession", canonical_profession)
                .eq("learned_synonym", learned_synonym)
                .execute(),
                label="synonym_learner.get_existing"
            )

            if result.data:
                return result.data[0]

        except Exception as e:
            logger.warning(f"⚠️ Error buscando aprendizaje existente: {e}")

        return None

    async def _update_existing_learned(
        self,
        existing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza un aprendizaje existente incrementando match_count."""
        try:
            new_match_count = existing.get("match_count", 1) + 1
            new_confidence = self._recalculate_confidence(existing, new_match_count)

            updated = await run_supabase(
                lambda: self.supabase.table("learned_synonyms")
                .update({
                    "match_count": new_match_count,
                    "confidence_score": new_confidence,
                    "last_seen_at": "NOW()"
                })
                .eq("id", existing["id"])
                .execute(),
                label="synonym_learner.update_existing"
            )

            if updated.data:
                logger.info(
                    f"🔄 [LEARNING] Aprendizaje actualizado: '{existing['learned_synonym']}' "
                    f"(match_count: {new_match_count}, confidence: {new_confidence:.2f})"
                )
                return updated.data[0]

        except Exception as e:
            logger.error(f"❌ Error actualizando aprendizaje: {e}")

        return existing

    def _calculate_confidence_score(
        self,
        query: str,
        matched_profession: str,
        num_results: int,
        context: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """
        Calcula el confidence score inicial (0.00 a 1.00).

        Factores:
        1. Número de resultados (más resultados = más confianza)
        2. Longitud del query (no muy corto, no muy largo)
        3. Exactitud del match (si contiene parte de la profesión)
        4. Método de expansión usado (AI > dynamic > static)
        """
        confidence = Decimal("0.50")  # Base confidence

        # Factor 1: Número de resultados
        if num_results >= 10:
            confidence += Decimal("0.20")
        elif num_results >= 5:
            confidence += Decimal("0.10")
        elif num_results >= 2:
            confidence += Decimal("0.05")

        # Factor 2: Longitud del query
        query_len = len(query.split())
        if 2 <= query_len <= 4:  # Ideal
            confidence += Decimal("0.10")
        elif query_len > 6:  # Muy largo
            confidence -= Decimal("0.10")

        # Factor 3: Exactitud del match
        query_lower = query.lower()
        profession_lower = matched_profession.lower()

        # Si el query contiene parte de la profesión
        if any(word in profession_lower for word in query_lower.split()):
            confidence += Decimal("0.15")

        # Factor 4: Método de expansión
        expansion_method = context.get("expansion_method") if context else None
        if expansion_method == "ai":
            confidence += Decimal("0.10")
        elif expansion_method == "dynamic":
            confidence += Decimal("0.05")

        # Limitar rango [0.00, 1.00]
        confidence = max(Decimal("0.00"), min(Decimal("1.00"), confidence))

        return confidence

    def _recalculate_confidence(
        self,
        existing: Dict[str, Any],
        new_match_count: int
    ) -> Decimal:
        """Recalcula confidence basado en match_count acumulado."""
        current_confidence = Decimal(str(existing.get("confidence_score", 0.50)))

        # Cada match adicional incrementa confianza
        # pero con diminishing returns
        increment = Decimal("0.05") / (new_match_count ** 0.5)

        new_confidence = current_confidence + increment

        # Limitar a 1.00
        return min(Decimal("1.00"), new_confidence)

    async def _check_existing_in_service_synonyms(
        self,
        canonical_profession: str,
        synonym: str
    ) -> bool:
        """Verifica si ya existe en service_synonyms."""
        try:
            result = await run_supabase(
                lambda: self.supabase.table("service_synonyms")
                .select("*")
                .eq("canonical_profession", canonical_profession)
                .eq("synonym", synonym)
                .execute(),
                label="synonym_learner.check_existing_service"
            )

            return len(result.data) > 0

        except Exception as e:
            logger.warning(f"⚠️ Error verificando service_synonyms: {e}")
            return False

    async def _insert_to_service_synonyms(
        self,
        canonical_profession: str,
        synonym: str
    ) -> bool:
        """Inserta automáticamente en service_synonyms."""
        try:
            result = await run_supabase(
                lambda: self.supabase.table("service_synonyms")
                .insert({
                    "canonical_profession": canonical_profession,
                    "synonym": synonym,
                    "active": True
                })
                .execute(),
                label="synonym_learner.insert_to_service_synonyms"
            )

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"❌ Error insertando en service_synonyms: {e}")
            return False

    async def _insert_learned_synonym_audit(
        self,
        canonical_profession: str,
        learned_synonym: str,
        source_query: str,
        confidence_score: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Inserta registro de auditoría en learned_synonyms (status='approved')."""
        try:
            result = await run_supabase(
                lambda: self.supabase.table("learned_synonyms")
                .insert({
                    "canonical_profession": canonical_profession,
                    "learned_synonym": learned_synonym,
                    "source_query": source_query,
                    "confidence_score": float(confidence_score),
                    "match_count": 1,
                    "status": "approved",
                    "approved_by": "system_auto",
                    "approved_at": "NOW()"
                })
                .execute(),
                label="synonym_learner.insert_audit"
            )

            if result.data:
                return result.data[0]

        except Exception as e:
            logger.warning(f"⚠️ Error insertando auditoría (no crítico): {e}")

        return None

    # ============================================================================
    # MÉTODOS DE AUDITORÍA (SISTEMA AUTOMÁTICO)
    # ============================================================================

    async def get_learning_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de aprendizaje automático."""
        try:
            # Total aprendidos (todos con status='approved')
            result = await run_supabase(
                lambda: self.supabase.table("learned_synonyms")
                .select("*")
                .eq("status", "approved")
                .execute(),
                label="synonym_learner.stats"
            )

            total_auto_learned = len(result.data) if result.data else 0

            # Top profesiones más aprendidas
            top_result = await run_supabase(
                lambda: self.supabase.table("learned_synonyms")
                .select("canonical_profession")
                .eq("status", "approved")
                .execute(),
                label="synonym_learner.top_professions"
            )

            # Contar por profesión
            profession_counts = {}
            if top_result.data:
                for item in top_result.data:
                    prof = item.get("canonical_profession", "unknown")
                    profession_counts[prof] = profession_counts.get(prof, 0) + 1

            # Ordenar top 5
            top_professions = sorted(
                profession_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            return {
                "total_auto_learned": total_auto_learned,
                "learning_method": "automatic",
                "top_professions": [
                    {"profession": prof, "count": count}
                    for prof, count in top_professions
                ]
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas: {e}")
            return {}


# ============================================================================
# INSTANCIA GLOBAL (se inicializa en main.py)
# ============================================================================

synonym_learner: Optional[SynonymLearner] = None


def initialize_synonym_learner(supabase_client) -> None:
    """Inicializa el sistema de aprendizaje de sinónimos.

    Args:
        supabase_client: Cliente Supabase
    """
    global synonym_learner

    if supabase_client:
        synonym_learner = SynonymLearner(supabase_client)
        logger.info("✅ SynonymLearner inicializado")
    else:
        synonym_learner = None
        logger.warning("⚠️ SynonymLearner deshabilitado (sin Supabase)")
