"""Cliente HTTP para verificar disponibilidad de proveedores"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
AV_PROVEEDORES_URL = os.getenv(
    "AV_PROVEEDORES_URL",
    "http://av-proveedores:8005"
)
AVAILABILITY_TIMEOUT_SECONDS = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "45"))
AVAILABILITY_ACCEPT_GRACE_SECONDS = float(
    os.getenv("AVAILABILITY_ACCEPT_GRACE_SECONDS", "2.0")
)


class ClienteDisponibilidad:
    """Cliente HTTP para verificar disponibilidad de proveedores"""

    def __init__(self):
        self.base_url = AV_PROVEEDORES_URL
        self.timeout = AVAILABILITY_TIMEOUT_SECONDS

    async def check_availability(
        self,
        *,
        req_id: str,
        service: str,
        city: Optional[str],
        candidates: List[Dict[str, Any]],
        redis_client,
    ) -> Dict[str, Any]:
        """
        Verifica disponibilidad de proveedores vía HTTP.

        Reemplaza al coordinador legacy de disponibilidad.
        """
        logger.info(
            f"📤 Verificando disponibilidad HTTP: req_id={req_id}, "
            f"servicio='{service}', ciudad={city or 'N/A'}, "
            f"{len(candidates)} candidatos"
        )

        # Preparar payload para av-proveedores
        payload = {
            "req_id": req_id,
            "servicio": service,
            "ciudad": city,
            "candidatos": candidates,
            "tiempo_espera_segundos": self.timeout,
        }

        try:
            # Llamada HTTP a av-proveedores
            async with httpx.AsyncClient(timeout=self.timeout + 5) as client:
                response = await client.post(
                    f"{self.base_url}/check-availability",
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"✅ Disponibilidad verificada: req_id={req_id}, "
                        f"accepted={len(data.get('accepted', []))}"
                    )
                    return {
                        "accepted": data.get("accepted", []),
                        "responded": data.get("responded", []),
                        "timeout": data.get("timeout", False),
                    }
                else:
                    logger.warning(
                        f"⚠️ Error HTTP verificando disponibilidad: "
                        f"status={response.status_code}"
                    )
                    return {"accepted": [], "responded": [], "timeout": True}

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout verificando disponibilidad: req_id={req_id}")
            return {"accepted": [], "responded": [], "timeout": True}
        except Exception as exc:
            logger.error(f"❌ Error verificando disponibilidad: {exc}")
            return {"accepted": [], "responded": [], "timeout": True}

    async def start_listener(self):
        """Método placeholder para compatibilidad con la interfaz anterior."""
        # No-op: el cliente HTTP no necesita listener
        pass


# Instancia global del cliente (singleton)
cliente_disponibilidad = ClienteDisponibilidad()
