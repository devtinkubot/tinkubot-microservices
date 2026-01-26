"""
Cliente HTTP para comunicarse con Search Service
"""

import logging
from typing import Any, Dict, Optional

import httpx

from config.configuracion import configuracion

logger = logging.getLogger(__name__)


class ClienteBusqueda:
    """Cliente para Search Service"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or f"http://ai-search:{configuracion.ai_search_port}"
        self.timeout = 10.0  # 10 segundos timeout

    async def search_providers(
        self,
        query: str,
        city: Optional[str] = None,
        limit: int = 10,
        use_ai_enhancement: bool = True,
    ) -> Dict[str, Any]:
        """
        Buscar proveedores en Search Service

        Args:
            query: Texto de búsqueda
            city: Ciudad para filtrar
            limit: Límite de resultados
            use_ai_enhancement: Usar mejora con IA

        Returns:
            Dict con resultados de búsqueda
        """
        try:
            payload = {
                "query": query,
                "limit": limit,
                "use_ai_enhancement": use_ai_enhancement,
            }

            # Agregar filtros si se proporcionan
            filters: Dict[str, Any] = {"verified_only": True}
            if city:
                filters["city"] = city.lower()  # Normalizar a minúsculas para case-insensitive

            payload["filters"] = filters

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/search", json=payload
                )
                response.raise_for_status()

                result = response.json()
                logger.info(
                    f"✅ Búsqueda en Search Service: {len(result.get('providers', []))} resultados "
                    f"(estrategia: {result.get('metadata', {}).get('search_strategy', 'unknown')})"
                )

                return self._convert_search_result_to_legacy_format(result)

        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ Error HTTP en Search Service: {e.response.status_code} - {e.response.text}"
            )
            return self._create_error_response(f"Error HTTP {e.response.status_code}")

        except httpx.TimeoutException:
            logger.error("⏰ Timeout en Search Service")
            return self._create_error_response("Timeout en Search Service")

        except Exception as e:
            logger.error(f"❌ Error comunicándose con Search Service: {e}")
            return self._create_error_response(str(e))

    def _convert_search_result_to_legacy_format(
        self, search_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convertir formato del Search Service al formato legado que espera ai-service-clientes
        """
        providers = search_result.get("providers", [])
        metadata = search_result.get("metadata", {})

        # Convertir proveedores al formato legado
        legacy_providers = []
        for provider in providers:
            legacy_provider = {
                "id": provider.get("id"),
                "phone_number": provider.get("phone_number"),
                "full_name": provider.get("full_name"),
                "name": provider.get("full_name"),
                "city": provider.get("city"),
                "rating": provider.get("rating", 0.0),
                "available": provider.get("available", True),
                "verified": provider.get("verified", False),
                "professions": provider.get("professions", []),
                "services": provider.get("services", []),
                "years_of_experience": provider.get("years_of_experience"),
                "created_at": provider.get("created_at"),
                "social_media_url": provider.get("social_media_url"),
                "social_media_type": provider.get("social_media_type"),
                "face_photo_url": provider.get("face_photo_url"),
                # Calcular score basado en rating y disponibilidad
                "score": self._calculate_legacy_score(provider),
            }
            legacy_providers.append(legacy_provider)

        return {
            "ok": True,
            "providers": legacy_providers,
            "total": len(legacy_providers),
            "search_metadata": {
                "strategy": metadata.get("search_strategy"),
                "search_time_ms": metadata.get("search_time_ms"),
                "confidence": metadata.get("confidence"),
                "used_ai_enhancement": metadata.get("used_ai_enhancement", False),
                "cache_hit": metadata.get("cache_hit", False),
            },
        }

    def _calculate_legacy_score(self, provider: Dict[str, Any]) -> float:
        """
        Calcular score legado basado en rating y otros factores
        """
        rating = provider.get("rating", 0.0)
        available = provider.get("available", True)
        verified = provider.get("verified", False)

        # Base: rating normalizado a 0-100
        score = (rating / 5.0) * 100

        # Bonificaciones
        if available:
            score += 20
        if verified:
            score += 10

        return min(100.0, score)

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Crear respuesta de error en formato legado
        """
        return {
            "ok": False,
            "providers": [],
            "total": 0,
            "error": error_message,
            "search_metadata": {
                "strategy": "error",
                "search_time_ms": 0,
                "confidence": 0.0,
                "used_ai_enhancement": False,
                "cache_hit": False,
            },
        }


# Instancia global del cliente
cliente_busqueda = ClienteBusqueda()
