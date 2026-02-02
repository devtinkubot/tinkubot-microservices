"""Disponibilidad de proveedores (implementación local)."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServicioDisponibilidad:
    """Servicio local para verificar disponibilidad de proveedores."""

    async def verificar_disponibilidad(
        self,
        *,
        req_id: str,
        servicio: str,
        ciudad: Optional[str],
        candidatos: List[Dict[str, Any]],
        cliente_redis: Any,
    ) -> Dict[str, Any]:
        """
        Verifica disponibilidad de proveedores.

        Actualmente no hay flujo de confirmación en tiempo real, por lo que
        mantiene el comportamiento existente: sin aceptados.
        """
        logger.info(
            "📍 Verificando disponibilidad local: req_id=%s, servicio='%s', ciudad=%s, %s candidatos",
            req_id,
            servicio,
            ciudad or "N/A",
            len(candidatos),
        )
        logger.warning("⚠️ Disponibilidad no implementada: retorna 0 aceptados")
        return {
            "aceptados": [],
            "respondidos": [],
            "tiempo_agotado": False,
        }


    async def start_listener(self) -> None:
        """Compatibilidad con la interfaz anterior."""
        return None


servicio_disponibilidad = ServicioDisponibilidad()
