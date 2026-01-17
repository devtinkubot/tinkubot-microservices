"""
Service Matching Service.

Orquesta el matching servicio → profesión → providers con scoring multi-dimensional.
Follows SOLID principles:
- SRP: Solo orquesta matching y scoring
- OCP: Extensible con nuevas estrategias de scoring
- DIP: Depende de abstracciones (Protocol)

Author: Claude Sonnet 4.5
Created: 2026-01-16
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from services.service_profession_mapper import ServiceProfessionMapper  # type: ignore
    from services.service_detector import ServiceDetector  # type: ignore


# ============================================
# Configuration
# ============================================

# Score mínimo para considerar un provider como relevante
# Providers con score < este threshold son filtrados
MIN_RELEVANCE_SCORE = 0.3


# ============================================
# Data Models
# ============================================

@dataclass
class ScoredProvider:
    """
    Provider con score de relevancia calculado.

    Attributes:
        provider_data: Datos crudos del provider desde la DB
        relevance_score: Score de relevancia calculado (0.0 a 1.0)
        service: Servicio que se buscó
        match_details: Detalles del cálculo del score
    """
    provider_data: Dict[str, Any]
    relevance_score: float = 0.0
    service: str = ""
    match_details: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Validar que el score esté en rango válido."""
        if not 0.0 <= self.relevance_score <= 1.0:
            raise ValueError(f"Relevance score must be between 0.0 and 1.0, got {self.relevance_score}")

    @property
    def id(self) -> str:
        """ID del provider."""
        return self.provider_data.get("id", "")

    @property
    def full_name(self) -> str:
        """Nombre completo del provider."""
        return self.provider_data.get("full_name", "")

    @property
    def profession(self) -> str:
        """Profesión del provider."""
        return self.provider_data.get("profession", "")

    @property
    def rating(self) -> float:
        """Rating del provider."""
        return self.provider_data.get("rating", 0.0)

    @property
    def services_list(self) -> List[str]:
        """Lista de servicios del provider."""
        return self.provider_data.get("services_list", [])

    def __repr__(self) -> str:
        """Representación legible."""
        return f"ScoredProvider(name={self.full_name}, profession={self.profession}, score={self.relevance_score:.2f})"


# ============================================
# Interfaces (Protocols) - Dependency Inversion
# ============================================

class ScoringStrategy(ABC):
    """
    Estrategia de scoring para providers.

    Permite extender el algoritmo de scoring sin modificar código existente.
    """

    @abstractmethod
    async def calculate_score(
        self,
        provider: Dict[str, Any],
        service: str,
        profession_scores: Dict[str, float],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calcular score de relevancia para un provider.

        Args:
            provider: Datos del provider
            service: Servicio buscado
            profession_scores: Scores de profesiones {profession: score}
            context: Contexto adicional opcional

        Returns:
            Tuple de (score_total, score_desglosado)
        """
        pass


class DefaultScoringStrategy(ScoringStrategy):
    """
    Estrategia de scoring por defecto.

    Score multi-dimensional:
    - Apropiación de profesión (35%)
    - Rating del provider (25%)
    - Experiencia (20%)
    - Especificidad del servicio (15%)
    - Verificación (5%)
    """

    async def calculate_score(
        self,
        provider: Dict[str, Any],
        service: str,
        profession_scores: Dict[str, float],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calcular score de relevancia usando algoritmo multi-dimensional.

        MEJORA: Verifica si el servicio está explícitamente mencionado en el catálogo.
        Si no está mencionado, aplica penalización drástica para evitar inferencias incorrectas.

        Args:
            provider: Datos del provider
            service: Servicio buscado
            profession_scores: Scores de profesiones
            context: Contexto adicional (no usado en estrategia por defecto)

        Returns:
            Tuple de (score_total, score_desglosado)
        """
        # Extraer datos del provider
        provider_profession = provider.get("profession", "").lower()
        rating = float(provider.get("rating", 0.0))
        experience_years = int(provider.get("experience_years", 0))
        verified = bool(provider.get("verified", False))
        services_list = provider.get("services_list", [])
        services_text = provider.get("services", "").lower()

        # Normalizar servicio para búsqueda
        service_lower = service.lower()

        # VERIFICACIÓN CRÍTICA: ¿Está el servicio explícitamente mencionado?
        service_explicitly_mentioned = (
            service_lower in services_text or
            service_lower in [s.lower() for s in services_list]
        )

        # Si el servicio NO está mencionado explícitamente, penalizar drásticamente
        if not service_explicitly_mentioned:
            # Score mínimo para inferencias (evita falsos positivos)
            return 0.05, {
                "profession_score": 0.0,
                "rating_score": 0.0,
                "experience_score": 0.0,
                "specificity_bonus": 0.0,
                "verification_score": 0.0,
                "service_mentioned": False,
                "inferred": True,
                "total": 0.05
            }

        # 1. Score de profesión apropiada (35%)
        profession_score = profession_scores.get(provider_profession, 0.5)
        profession_weighted = profession_score * 0.35

        # 2. Score de rating (25%)
        # Rating está en escala 0-5, normalizar a 0-1
        rating_score = min(rating / 5.0, 1.0)
        rating_weighted = rating_score * 0.25

        # 3. Score de experiencia (20%)
        # Asumimos que 10+ años es excelente
        experience_score = min(experience_years / 10.0, 1.0)
        experience_weighted = experience_score * 0.20

        # 4. Bonus de especificidad del servicio (15%)
        # Si el servicio está explícitamente mencionado, es un match fuerte
        specificity_bonus = 0.15

        # 5. Score de verificación (5%)
        verification_score = 1.0 if verified else 0.5
        verification_weighted = verification_score * 0.05

        # Score total
        total_score = (
            profession_weighted +
            rating_weighted +
            experience_weighted +
            specificity_bonus +
            verification_weighted
        )

        # Desglose para debugging
        score_breakdown = {
            "profession_score": profession_score,
            "rating_score": rating_score,
            "experience_score": experience_score,
            "specificity_bonus": specificity_bonus,
            "verification_score": verification_score,
            "service_mentioned": True,
            "inferred": False,
            "total": total_score
        }

        return total_score, score_breakdown


# ============================================
# Service Layer - Business Logic
# ============================================

class ServiceMatchingService:
    """
    Servicio principal de matching servicio → profesión → providers.

    Orquesta el proceso completo:
    1. Detectar servicio en el mensaje
    2. Obtener profesiones candidates con scores
    3. Buscar providers que ofrecen el servicio
    4. Calcular score de relevancia multi-dimensional
    5. Ordenar por relevancia

    Example:
        >>> matching = ServiceMatchingService(
        ...     detector=detector,
        ...     mapper=mapper,
        ...     repo=repo
        ... )
        >>> results = await matching.find_providers_for_service(
        ...     message="necesito inyecciones de vitaminas en cuenca",
        ...     city="cuenca"
        ... )
        >>> for provider in results:
        ...     print(f"{provider.full_name}: {provider.relevance_score:.2f}")
    """

    def __init__(
        self,
        detector: ServiceDetector,
        mapper: ServiceProfessionMapper,
        repo: Any,  # ProviderRepository
        scoring_strategy: Optional[ScoringStrategy] = None
    ):
        """
        Inicializar servicio de matching.

        Args:
            detector: ServiceDetector para detectar servicios en mensajes
            mapper: ServiceProfessionMapper para mapear servicios a profesiones
            repo: ProviderRepository para buscar providers
            scoring_strategy: Estrategia de scoring (opcional, usa DefaultScoringStrategy)
        """
        self.detector = detector
        self.mapper = mapper
        self.repo = repo
        self.scoring_strategy = scoring_strategy or DefaultScoringStrategy()

        logger.info("ServiceMatchingService initialized")

    async def find_providers_for_service(
        self,
        message: str,
        city: str,
        limit: int = 10
    ) -> List[ScoredProvider]:
        """
        Buscar providers para un servicio detectado en un mensaje.

        Este es el método principal que orquesta todo el flujo de matching.

        Args:
            message: Mensaje del usuario (ej: "necesito inyecciones en cuenca")
            city: Ciudad donde se busca el servicio
            limit: Máximo número de resultados (default: 10)

        Returns:
            Lista de ScoredProvider ordenados por relevancia descendente
        """
        logger.info(f"Starting service matching for message: '{message}' in city: '{city}'")

        # Step 1: Detectar servicio en el mensaje
        detection_result = await self.detector.detect_services(message)

        if not detection_result.has_services():
            logger.warning(f"No services detected in message: '{message}'")
            return []

        service = detection_result.primary_service or detection_result.services[0]
        logger.info(f"Detected service: '{service}' (confidence: {detection_result.confidence:.2f})")

        # Step 2: Obtener profesiones candidates con scores
        profession_mapping = await self.mapper.get_professions_for_service(service)

        if not profession_mapping:
            logger.warning(f"No profession mapping found for service: '{service}'")
            return []

        # Convertir a dict para fácil acceso
        profession_scores = {
            ps.profession: ps.score
            for ps in profession_mapping.professions
        }

        logger.info(
            f"Profession scores for '{service}': {profession_scores}"
        )

        # Step 3: Buscar providers que ofrecen el servicio
        providers_data = await self.repo.search_by_service_and_city(
            service=service,
            city=city,
            professions=list(profession_scores.keys()),
            limit=limit
        )

        if not providers_data:
            logger.warning(
                f"No providers found for service '{service}' in city '{city}'"
            )
            return []

        logger.info(f"Found {len(providers_data)} providers, calculating scores...")

        # Step 4: Calcular score de relevancia para cada provider
        scored_providers = []

        for provider_data in providers_data:
            # Calcular score usando la estrategia
            total_score, score_breakdown = await self.scoring_strategy.calculate_score(
                provider=provider_data,
                service=service,
                profession_scores=profession_scores
            )

            # Crear ScoredProvider
            scored_provider = ScoredProvider(
                provider_data=provider_data,
                relevance_score=total_score,
                service=service,
                match_details=score_breakdown
            )

            scored_providers.append(scored_provider)

            logger.debug(
                f"Provider {scored_provider.full_name} ({scored_provider.profession}): "
                f"score={total_score:.2f} | breakdown={score_breakdown}"
            )

        # Step 5: Filtrar providers con score mínimo aceptable
        scored_providers_filtered = [
            sp for sp in scored_providers
            if sp.relevance_score >= MIN_RELEVANCE_SCORE
        ]

        # Log filtered providers
        filtered_count = len(scored_providers) - len(scored_providers_filtered)
        if filtered_count > 0:
            logger.info(
                f"🔍 Filtered out {filtered_count} providers with score < {MIN_RELEVANCE_SCORE}"
            )
            for sp in scored_providers:
                if sp.relevance_score < MIN_RELEVANCE_SCORE:
                    logger.warning(
                        f"   ❌ {sp.full_name} ({sp.profession}): score={sp.relevance_score:.2f} "
                        f"(service_mentioned={sp.match_details.get('service_mentioned', False)})"
                    )

        # Step 6: Ordenar por relevancia descendente
        scored_providers_filtered.sort(key=lambda p: p.relevance_score, reverse=True)

        if scored_providers_filtered:
            logger.info(
                f"✅ Returning {len(scored_providers_filtered)} providers, "
                f"top score: {scored_providers_filtered[0].relevance_score:.2f}"
            )
        else:
            logger.warning(
                f"⚠️ No providers met the minimum score threshold ({MIN_RELEVANCE_SCORE})"
            )

        return scored_providers_filtered[:limit]

    async def find_providers_for_direct_service(
        self,
        service: str,
        city: str,
        limit: int = 10
    ) -> List[ScoredProvider]:
        """
        Buscar providers para un servicio específico (sin detección de mensaje).

        Útil cuando el servicio ya está identificado.

        Args:
            service: Servicio específico (ej: "inyección", "suero")
            city: Ciudad donde se busca
            limit: Máximo número de resultados

        Returns:
            Lista de ScoredProvider ordenados por relevancia
        """
        logger.info(f"Direct service search for: '{service}' in city: '{city}'")

        # Step 1: Obtener profesiones candidates
        profession_mapping = await self.mapper.get_professions_for_service(service)

        if not profession_mapping:
            logger.warning(f"No profession mapping found for service: '{service}'")
            return []

        profession_scores = {
            ps.profession: ps.score
            for ps in profession_mapping.professions
        }

        # Step 2: Buscar providers
        providers_data = await self.repo.search_by_service_and_city(
            service=service,
            city=city,
            professions=list(profession_scores.keys()),
            limit=limit
        )

        if not providers_data:
            return []

        # Step 3 & 4: Calcular scores
        scored_providers = []

        for provider_data in providers_data:
            total_score, score_breakdown = await self.scoring_strategy.calculate_score(
                provider=provider_data,
                service=service,
                profession_scores=profession_scores
            )

            scored_providers.append(ScoredProvider(
                provider_data=provider_data,
                relevance_score=total_score,
                service=service,
                match_details=score_breakdown
            ))

        # Step 5: Filtrar por score mínimo
        scored_providers_filtered = [
            sp for sp in scored_providers
            if sp.relevance_score >= MIN_RELEVANCE_SCORE
        ]

        # Log filtrado
        filtered_count = len(scored_providers) - len(scored_providers_filtered)
        if filtered_count > 0:
            logger.info(
                f"🔍 Filtered out {filtered_count} providers with score < {MIN_RELEVANCE_SCORE}"
            )

        # Step 6: Ordenar
        scored_providers_filtered.sort(key=lambda p: p.relevance_score, reverse=True)

        return scored_providers_filtered[:limit]


# ============================================
# Singleton Instance
# ============================================

_service_matching_service: Optional[ServiceMatchingService] = None


def get_service_matching_service(
    detector: ServiceDetector,
    mapper: ServiceProfessionMapper,
    repo: Any,
    scoring_strategy: Optional[ScoringStrategy] = None
) -> ServiceMatchingService:
    """
    Retorna instancia global del ServiceMatchingService (singleton).

    Args:
        detector: ServiceDetector
        mapper: ServiceProfessionMapper
        repo: ProviderRepository
        scoring_strategy: Estrategia de scoring opcional

    Returns:
        Instancia única de ServiceMatchingService

    Example:
        >>> from services.service_matching import get_service_matching_service
        >>> matching = get_service_matching_service(detector, mapper, repo)
        >>> results = await matching.find_providers_for_service("necesito inyecciones", "cuenca")
    """
    global _service_matching_service

    if _service_matching_service is None:
        _service_matching_service = ServiceMatchingService(
            detector=detector,
            mapper=mapper,
            repo=repo,
            scoring_strategy=scoring_strategy
        )
        logger.info("✅ ServiceMatchingService singleton initialized")

    return _service_matching_service
