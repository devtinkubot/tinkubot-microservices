"""Servicio de búsqueda de proveedores."""

import logging
from typing import Any, Dict, List, Optional

from infrastructure.clientes.busqueda import ClienteBusqueda


class BuscadorProveedores:
    """
    Servicio de dominio para buscar proveedores.

    Coordina la búsqueda con el Search Service y la validación con IA
    para retornar solo proveedores relevantes y validados.
    """

    def __init__(
        self,
        search_client: ClienteBusqueda,
        ai_validator: 'IValidadorIA',
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de búsqueda.

        Args:
            search_client: Cliente para Search Service
            ai_validator: Servicio de validación con IA
            logger: Logger para trazabilidad
        """
        self.search_client = search_client
        self.ai_validator = ai_validator
        self.logger = logger

    async def buscar(
        self,
        profesion: str,
        ciudad: str,
        radio_km: float = 10.0,
        terminos_expandidos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Buscar proveedores usando Search Service + validación IA.

        Flujo:
        1. Búsqueda token-based rápida (sin AI-Enhanced)
        2. Validación con IA para filtrar proveedores que REALMENTE pueden ayudar
        3. Retornar solo proveedores validados

        Args:
            profesion: Profesión/servicio a buscar
            ciudad: Ciudad donde buscar
            radio_km: Radio de búsqueda en km (no usado actualmente)
            terminos_expandidos: Términos expandidos por IA para mejorar búsqueda

        Returns:
            Dict con:
                - ok: bool si la búsqueda fue exitosa
                - providers: lista de proveedores validados
                - total: cantidad de proveedores
                - search_scope: ámbito de búsqueda
        """
        # Usar términos expandidos por IA si están disponibles
        if terminos_expandidos and len(terminos_expandidos) > 1:
            # Usar términos expandidos por IA
            terms_joined = " ".join(terminos_expandidos)
            query = f"{terms_joined} en {ciudad}"
            self.logger.info(
                f"🔍 Búsqueda con términos expandidos ({len(terminos_expandidos)} términos): "
                f"profession='{profesion}', location='{ciudad}'"
            )
        else:
            # Comportamiento original (backward compatible)
            query = f"{profesion} en {ciudad}"
            self.logger.info(
                f"🔍 Búsqueda con validación IA: profession='{profesion}', location='{ciudad}'"
            )

        try:
            # Búsqueda token-based (rápida, sin IA-Enhanced)
            result = await self.search_client.search_providers(
                query=query,
                city=ciudad,
                limit=10,
                use_ai_enhancement=False,  # ✅ Solo token-based (sin IA)
            )

            if not result.get("ok"):
                error = result.get("error", "Error desconocido")
                self.logger.warning(f"⚠️ Search Service falló: {error}")
                return {"ok": False, "providers": [], "total": 0}

            providers = result.get("providers", [])
            total = result.get("total", len(providers))

            metadata = result.get("search_metadata", {})
            self.logger.info(
                f"✅ Búsqueda local en {ciudad}: {total} proveedores "
                f"(estrategia: {metadata.get('strategy')}, "
                f"tiempo: {metadata.get('search_time_ms')}ms)"
            )

            # Si no hay proveedores, retornar vacío
            if not providers:
                return {"ok": True, "providers": [], "total": 0}

            # NUEVO: Validar con IA antes de devolver
            validated_providers = await self.ai_validator.validar_proveedores(
                user_need=profesion,
                providers=providers,
            )

            self.logger.info(
                f"🎯 Validación final: {len(validated_providers)}/{total} "
                f"proveedores pasaron validación IA"
            )

            return {
                "ok": True,
                "providers": validated_providers,
                "total": len(validated_providers),
                "search_scope": "local",
            }

        except Exception as exc:
            self.logger.error(f"❌ Error en búsqueda: {exc}")
            return {"ok": False, "providers": [], "total": 0}
