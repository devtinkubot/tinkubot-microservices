"""
Service Detector Service - Versión 100% Dinámica.

Detecta servicios específicos en mensajes del usuario usando SOLO datos de Supabase.
NO tiene datos hardcoded - todo es dinámico vía ServiceProfessionMapper.

Author: Claude Sonnet 4.5
Updated: 2026-01-17
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from services.service_profession_mapper import ServiceProfessionMapper

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass(frozen=True)
class ServiceDetectionResult:
    """
    Resultado de la detección de servicios en un mensaje.

    Attributes:
        services: Lista de servicios detectados
        primary_service: Servicio más importante/relevante
        confidence: Nivel de confianza (0.0 a 1.0)
        raw_message: Mensaje original
        normalized_message: Mensaje normalizado (minúsculas, sin tildes)
    """
    services: List[str] = field(default_factory=list)
    primary_service: Optional[str] = None
    confidence: float = 0.0
    raw_message: str = ""
    normalized_message: str = ""

    def __post_init__(self):
        """Validar que el confidence esté en rango válido."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def has_services(self) -> bool:
        """Verifica si se detectaron servicios."""
        return len(self.services) > 0

    def __repr__(self):
        """Representación legible."""
        services_str = ", ".join(self.services) if self.services else "none"
        return f"ServiceDetectionResult(services=[{services_str}], confidence={self.confidence:.2f})"


# ============================================
# Service Layer
# ============================================

class ServiceDetectorService:
    """
    Servicio para detectar servicios específicos en mensajes del usuario.

    100% DINÁMICO - NO usa datos hardcoded.
    Todo el conocimiento de servicios viene de Supabase vía ServiceProfessionMapper.

    Estrategia:
    1. Busca cada palabra del mensaje en ServiceProfessionMapper (DB)
    2. Valida que el servicio tenga mapeos a profesiones
    3. No hay diccionarios ni patrones estáticos

    Example:
        >>> detector = ServiceDetectorService(mapper=profession_mapper)
        >>> result = await detector.detect_services("necesito inyecciones en cuenca")
        >>> print(result.services)  # ["inyecciones"]
        >>> print(result.primary_service)  # "inyecciones"
    """

    # Stopwords en español que no son servicios
    STOPWORDS: Set[str] = {
        "de", "del", "la", "el", "en", "por", "para", "con",
        "una", "un", "unas", "unos",
        "que", "quiero", "necesito", "busco", "requiero",
        "cuenca", "quito", "guayaquil",  # Ciudades comunes
        "favor", "por favor", "urgente", "ya",
        "y", "o", "a", "ante", "bajo", "cabe", "contra",
        "desde", "durante", "hacia", "hasta", "mediante",
        "mientras", "ni", "según", "sin", "sobre", "tras",
        "tu", "yo", "me", "mi", "mis", "sus", "su",
    }

    def __init__(
        self,
        profession_mapper: Optional[ServiceProfessionMapper] = None
    ):
        """
        Inicializar detector de servicios.

        Args:
            profession_mapper: Requerido para validar servicios detectados
        """
        self.profession_mapper = profession_mapper
        if not profession_mapper:
            raise ValueError("profession_mapper es REQUERIDO para ServiceDetectorService")
        logger.debug("ServiceDetectorService initialized (DB-only, no hardcoded data)")

    async def detect_services(
        self,
        message: str,
        use_mapper_validation: bool = True
    ) -> ServiceDetectionResult:
        """
        Detecta servicios en un mensaje del usuario.

        100% dinámico - Todo viene de Supabase.

        Args:
            message: Mensaje del usuario
            use_mapper_validation: Si es True, valida servicios con ServiceProfessionMapper

        Returns:
            ServiceDetectionResult con servicios detectados
        """
        if not message or not message.strip():
            return ServiceDetectionResult(
                raw_message=message,
                normalized_message="",
                confidence=0.0
            )

        # Normalizar mensaje
        normalized = self._normalize_message(message)

        # Detectar servicios desde ServiceProfessionMapper (DB)
        detected_services = set()

        if use_mapper_validation and self.profession_mapper:
            mapper_services = await self._detect_from_mapper(normalized)
            detected_services.update(mapper_services)

            # Validar servicios detectados
            validated_services = await self._validate_with_mapper(detected_services)
            detected_services = validated_services
        else:
            logger.warning("ServiceProfessionMapper no proporcionado, sin validación")

        # Convertir a lista ordenada
        services_list = sorted(list(detected_services))

        # Determinar servicio primario
        primary = self._determine_primary_service(services_list, normalized)

        # Calcular confianza
        confidence = self._calculate_confidence(services_list, normalized)

        result = ServiceDetectionResult(
            services=services_list,
            primary_service=primary,
            confidence=confidence,
            raw_message=message,
            normalized_message=normalized
        )

        if result.has_services():
            logger.info(
                f"Detected {len(services_list)} services: {services_list} "
                f"(primary: {primary}, confidence: {confidence:.2f})"
            )
        else:
            logger.debug(f"No services detected in message: {message[:50]}...")

        return result

    def _normalize_message(self, message: str) -> str:
        """
        Normalizar mensaje para mejor detección.

        - Minúsculas
        - Remover tildes
        - Remover puntuación excesiva
        """
        import unicodedata

        # Minúsculas
        normalized = message.lower().strip()

        # Remover tildes
        normalized = unicodedata.normalize('NFKD', normalized)
        normalized = ''.join(
            c for c in normalized
            if not unicodedata.combining(c)
        )

        # Remover punctuation excesiva (pero mantener espacios)
        normalized = re.sub(r'[!?;:,\.\']+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    async def _detect_from_mapper(
        self,
        normalized_message: str
    ) -> Set[str]:
        """
        Detectar servicios buscando directamente en ServiceProfessionMapper.

        Busca cada palabra del mensaje en la lista de servicios de la DB.
        Esto permite detectar servicios no médicos como electricista, plomero, etc.

        Args:
            normalized_message: Mensaje normalizado

        Returns:
            Set de servicios detectados
        """
        detected = set()

        if not self.profession_mapper:
            return detected

        # Palabras del mensaje
        words = normalized_message.split()

        # Buscar cada palabra en los servicios del mapper
        for word in words:
            if word in self.STOPWORDS:
                continue

            try:
                mapping = await self.profession_mapper.get_professions_for_service(word)
                if mapping and mapping.professions:
                    detected.add(word)
                    logger.debug(f"Detected service from mapper: '{word}'")
            except Exception:
                pass  # Servicio no encontrado en mapper

        return detected

    async def _validate_with_mapper(
        self,
        detected_services: Set[str]
    ) -> Set[str]:
        """
        Validar servicios detectados con ServiceProfessionMapper.

        Solo mantiene servicios que tienen mapeos conocidos.

        Args:
            detected_services: Servicios detectados

        Returns:
            Set de servicios validados
        """
        if not self.profession_mapper:
            return detected_services

        validated = set()

        for service in detected_services:
            try:
                mapping = await self.profession_mapper.get_professions_for_service(service)
                if mapping and mapping.professions:
                    validated.add(service)
                    logger.debug(f"Service '{service}' validated with {len(mapping.professions)} professions")
                else:
                    logger.debug(f"Service '{service}' not found in mapper")
            except Exception as e:
                logger.warning(f"Error validating service '{service}': {e}")

        return validated if validated else detected_services

    def _determine_primary_service(
        self,
        services: List[str],
        normalized_message: str
    ) -> Optional[str]:
        """
        Determinar el servicio primario de la lista.

        Prioridades:
        1. Servicio que aparece primero en el mensaje
        2. Servicio más específico (más largo)
        3. Primer servicio de la lista

        Args:
            services: Lista de servicios detectados
            normalized_message: Mensaje normalizado

        Returns:
            Servicio primario o None
        """
        if not services:
            return None

        # Buscar posición de cada servicio en el mensaje
        service_positions = []
        for service in services:
            pos = normalized_message.find(service)
            if pos != -1:
                service_positions.append((service, pos))

        if not service_positions:
            return services[0]

        # Ordenar por posición (aparece primero = más importante)
        service_positions.sort(key=lambda x: x[1])

        # Si hay empate en posición, elegir el más largo (más específico)
        primary = service_positions[0][0]
        for service, pos in service_positions:
            if pos == service_positions[0][1] and len(service) > len(primary):
                primary = service

        return primary

    def _calculate_confidence(
        self,
        services: List[str],
        normalized_message: str
    ) -> float:
        """
        Calcular nivel de confianza de la detección.

        Factores:
        - Cantidad de servicios detectados
        - Presencia de palabras clave claras (eliminado - ya no se usa hardcoded)
        - Especificidad del mensaje

        Args:
            services: Lista de servicios detectados
            normalized_message: Mensaje normalizado

        Returns:
            Confianza entre 0.0 y 1.0
        """
        if not services:
            return 0.0

        confidence = 0.0

        # Factor 1: Cantidad de servicios (máximo 0.3)
        service_count_score = min(len(services) * 0.1, 0.3)
        confidence += service_count_score

        # Factor 2: Especificidad del mensaje (máximo 0.7)
        message_words = len(normalized_message.split())
        if message_words >= 4:
            confidence += 0.7
        elif message_words >= 2:
            confidence += 0.3
        elif message_words >= 1:
            confidence += 0.1

        return min(confidence, 1.0)


# ============================================
# Singleton Instance
# ============================================

_service_detector: Optional[ServiceDetectorService] = None


def get_service_detector(
    profession_mapper: Optional[ServiceProfessionMapper] = None
) -> ServiceDetectorService:
    """
    Retorna instancia global del ServiceDetectorService (singleton).

    Args:
        profession_mapper: Requerido, ServiceProfessionMapper para validación

    Returns:
        Instancia única de ServiceDetectorService

    Example:
        >>> from services.service_detector import get_service_detector
        >>> mapper = get_service_profession_mapper(supabase, redis)
        >>> detector = get_service_detector(mapper)
        >>> result = await detector.detect_services("necesito inyecciones")
    """
    global _service_detector

    if _service_detector is None:
        _service_detector = ServiceDetectorService(
            profession_mapper=profession_mapper
        )
        logger.info("✅ ServiceDetectorService singleton initialized")

    return _service_detector
