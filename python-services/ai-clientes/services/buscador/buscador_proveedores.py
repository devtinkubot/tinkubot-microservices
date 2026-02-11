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
        cliente_busqueda: ClienteBusqueda,
        validador_ia: 'IValidadorIA',
        logger: logging.Logger,
    ):
        """
        Inicializar el servicio de búsqueda.

        Args:
            cliente_busqueda: Cliente para Search Service
            validador_ia: Servicio de validación con IA
            logger: Logger para trazabilidad
        """
        self.cliente_busqueda = cliente_busqueda
        self.validador_ia = validador_ia
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
            terminos_unidos = " ".join(terminos_expandidos)
            consulta = f"{terminos_unidos}"
            self.logger.info(
                f"🔍 Búsqueda con términos expandidos ({len(terminos_expandidos)} términos): "
                f"profession='{profesion}', location='{ciudad}'"
            )
        else:
            # Comportamiento original (backward compatible)
            consulta = f"{profesion}"
            self.logger.info(
                f"🔍 Búsqueda con validación IA: profession='{profesion}', location='{ciudad}'"
            )

        try:
            # Búsqueda token-based (rápida, sin IA-Enhanced)
            resultado = await self.cliente_busqueda.buscar_proveedores(
                consulta=consulta,
                ciudad=ciudad,
                limite=10,
                usar_mejora_ia=False,  # ✅ Solo token-based (sin IA)
            )

            if not resultado.get("ok"):
                error = resultado.get("error", "Error desconocido")
                self.logger.warning(f"⚠️ Search Service falló: {error}")
                return {"ok": False, "providers": [], "total": 0}

            proveedores = resultado.get("providers", [])
            total = resultado.get("total", len(proveedores))

            metadatos = resultado.get("search_metadata", {})
            self.logger.info(
                f"✅ Búsqueda local en {ciudad}: {total} proveedores "
                f"(estrategia: {metadatos.get('strategy')}, "
                f"tiempo: {metadatos.get('search_time_ms')}ms)"
            )

            # Si no hay proveedores, retornar vacío
            if not proveedores:
                return {"ok": True, "providers": [], "total": 0}

            # NUEVO: Validar con IA antes de devolver
            proveedores_validados = await self.validador_ia.validar_proveedores(
                necesidad_usuario=profesion,
                proveedores=proveedores,
            )

            self.logger.info(
                f"🎯 Validación final: {len(proveedores_validados)}/{total} "
                f"proveedores pasaron validación IA"
            )

            return {
                "ok": True,
                "providers": proveedores_validados,
                "total": len(proveedores_validados),
                "search_scope": "local",
            }

        except Exception as exc:
            self.logger.error(f"❌ Error en búsqueda: {exc}")
            return {"ok": False, "providers": [], "total": 0}
