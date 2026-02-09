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

    async def buscar_proveedores(
        self,
        consulta: str,
        ciudad: Optional[str] = None,
        limite: int = 10,
        usar_mejora_ia: bool = True,
    ) -> Dict[str, Any]:
        """
        Buscar proveedores en Search Service

        Args:
            consulta: Texto de búsqueda
            ciudad: Ciudad para filtrar
            limite: Límite de resultados
            usar_mejora_ia: Usar mejora con IA

        Returns:
            Dict con resultados de búsqueda
        """
        try:
            carga = {
                "query": consulta,
                "limit": limite,
                "use_ai_enhancement": usar_mejora_ia,
            }

            # Agregar filtros si se proporcionan
            filtros: Dict[str, Any] = {"verified_only": True}
            if ciudad:
                filtros["city"] = ciudad.lower()  # Normalizar a minúsculas para case-insensitive

            carga["filters"] = filtros

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                respuesta = await client.post(
                    f"{self.base_url}/api/v1/search", json=carga
                )
                respuesta.raise_for_status()

                resultado = respuesta.json()
                logger.info(
                    f"✅ Búsqueda en Search Service: {len(resultado.get('providers', []))} resultados "
                    f"(estrategia: {resultado.get('metadata', {}).get('search_strategy', 'unknown')})"
                )

                return self._convertir_resultado_busqueda_a_formato_legacy(resultado)

        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ Error HTTP en Search Service: {e.response.status_code} - {e.response.text}"
            )
            return self._crear_respuesta_error(f"Error HTTP {e.response.status_code}")

        except httpx.TimeoutException:
            logger.error("⏰ Timeout en Search Service")
            return self._crear_respuesta_error("Timeout en Search Service")

        except Exception as exc:
            logger.error(f"❌ Error comunicándose con Search Service: {exc}")
            return self._crear_respuesta_error(str(exc))

    def _convertir_resultado_busqueda_a_formato_legacy(
        self, resultado_busqueda: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convertir formato del Search Service al formato legado que espera ai-service-clientes
        """
        proveedores = resultado_busqueda.get("providers", [])
        metadatos = resultado_busqueda.get("metadata", {})

        # Convertir proveedores al formato legado
        proveedores_legacy = []
        for proveedor in proveedores:
            proveedor_legacy = {
                "id": proveedor.get("id"),
                "phone_number": proveedor.get("phone_number"),
                "real_phone": proveedor.get("real_phone") or proveedor.get("phone_number"),
                "full_name": proveedor.get("full_name"),
                "name": proveedor.get("full_name"),
                "city": proveedor.get("city"),
                "rating": proveedor.get("rating", 0.0),
                "available": proveedor.get("available", True),
                "verified": proveedor.get("verified", False),
                "professions": proveedor.get("professions", []),
                "services": proveedor.get("services", []),
                "years_of_experience": proveedor.get("years_of_experience"),
                "created_at": proveedor.get("created_at"),
                "social_media_url": proveedor.get("social_media_url"),
                "social_media_type": proveedor.get("social_media_type"),
                "face_photo_url": proveedor.get("face_photo_url"),
                # Calcular score basado en rating y disponibilidad
                "score": self._calcular_puntaje_legacy(proveedor),
            }
            proveedores_legacy.append(proveedor_legacy)

        return {
            "ok": True,
            "providers": proveedores_legacy,
            "total": len(proveedores_legacy),
            "search_metadata": {
                "strategy": metadatos.get("search_strategy"),
                "search_time_ms": metadatos.get("search_time_ms"),
                "confidence": metadatos.get("confidence"),
                "used_ai_enhancement": metadatos.get("used_ai_enhancement", False),
                "cache_hit": metadatos.get("cache_hit", False),
            },
        }

    def _calcular_puntaje_legacy(self, proveedor: Dict[str, Any]) -> float:
        """
        Calcular score legado basado en rating y otros factores
        """
        calificacion = proveedor.get("rating", 0.0)
        disponible = proveedor.get("available", True)
        verificado = proveedor.get("verified", False)

        # Base: rating normalizado a 0-100
        puntaje = (calificacion / 5.0) * 100

        # Bonificaciones
        if disponible:
            puntaje += 20
        if verificado:
            puntaje += 10

        return min(100.0, puntaje)

    def _crear_respuesta_error(self, mensaje_error: str) -> Dict[str, Any]:
        """
        Crear respuesta de error en formato legado
        """
        return {
            "ok": False,
            "providers": [],
            "total": 0,
            "error": mensaje_error,
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
