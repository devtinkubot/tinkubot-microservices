"""Servicio de búsqueda de proveedores."""

import logging
from typing import Any, Dict, Optional, Protocol

from config.configuracion import configuracion
from infrastructure.clientes.busqueda import ClienteBusqueda
from utils.texto import normalizar_texto_para_coincidencia


class IValidadorIA(Protocol):
    async def validar_proveedores(
        self,
        necesidad_usuario: str,
        descripcion_problema: Optional[str],
        proveedores: list[Dict[str, Any]],
        request_domain_code: Optional[str] = None,
        request_category_name: Optional[str] = None,
        request_domain: Optional[str] = None,
        request_category: Optional[str] = None,
        search_profile: Optional[Dict[str, Any]] = None,
    ) -> list[Dict[str, Any]]: ...


def _tokens_from_text(text: str) -> list[str]:
    normalized = normalizar_texto_para_coincidencia(text or "")
    return [token for token in normalized.split() if len(token) >= 3]


def _build_search_profile_from_inputs(
    *,
    primary_service: str,
    service_summary: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    raw_input: str = "",
) -> Dict[str, Any]:
    signals: list[str] = []
    for value in (service_summary, primary_service, domain, category):
        if value:
            candidate = value.strip()
            if candidate and candidate not in signals:
                signals.append(candidate)
    for token in _tokens_from_text(raw_input):
        if len(signals) >= 6:
            break
        if token not in signals:
            signals.append(token)
    return {
        "primary_service": primary_service,
        "service_summary": service_summary,
        "domain": domain,
        "category": category,
        "signals": signals,
        "raw_input": raw_input.strip(),
        "confidence": 0.85,
        "source": "client",
    }


class BuscadorProveedores:
    """
    Servicio de dominio para buscar proveedores.

    Coordina la búsqueda con el Search Service y la validación con IA
    para retornar solo proveedores relevantes y validados.
    """

    def __init__(
        self,
        cliente_busqueda: ClienteBusqueda,
        validador_ia: IValidadorIA,
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
        descripcion_problema: Optional[str] = None,
        domain: Optional[str] = None,
        domain_code: Optional[str] = None,
        category: Optional[str] = None,
        category_name: Optional[str] = None,
        search_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Buscar proveedores usando Search Service + validación IA.

        Flujo:
        1. Búsqueda embeddings-only en Search Service
        2. Validación con IA para filtrar proveedores que REALMENTE pueden ayudar
        3. Retornar solo proveedores validados

        Args:
            profesion: Profesión/servicio a buscar
            ciudad: Ciudad donde buscar
            radio_km: Radio de búsqueda en km (no usado actualmente)
            descripcion_problema: Contexto completo del problema del cliente

        Returns:
            Dict con:
                - ok: bool si la búsqueda fue exitosa
                - providers: lista de proveedores validados
                - total: cantidad de proveedores
                - search_scope: ámbito de búsqueda
        """
        profile = search_profile or _build_search_profile_from_inputs(
            primary_service=profesion,
            service_summary=None,
            domain=domain or domain_code,
            category=category or category_name,
            raw_input=descripcion_problema or profesion,
        )
        service_summary = str(
            profile.get("service_summary") or profile.get("primary_service") or ""
        ).strip()
        profile["service_summary"] = service_summary or None
        consulta = self._build_canonical_query(
            profesion=str(profile.get("primary_service") or profesion),
            service_summary=service_summary or None,
            descripcion_problema=descripcion_problema,
            domain=str(profile.get("domain") or domain or ""),
            domain_code=domain_code,
            category=str(profile.get("category") or category or ""),
            category_name=category_name,
        )
        self.logger.info(
            "🔍 Búsqueda embeddings + validación IA: "
            "service='%s', query='%s', location='%s'",
            profesion,
            consulta,
            ciudad,
        )

        try:
            # Búsqueda embeddings-only
            resultado = await self.cliente_busqueda.buscar_proveedores(
                consulta=consulta,
                ciudad=ciudad,
                descripcion_problema=descripcion_problema or profesion,
                service_candidate=profesion,
                domain=domain,
                category=category,
                domain_code=domain_code,
                category_name=category_name,
                search_profile=profile,
                limite=configuracion.search_candidate_limit,
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

            if proveedores:
                resumen_scores = [
                    {
                        "provider_id": proveedor.get("id"),
                        "similarity_score": proveedor.get("similarity_score"),
                        "services": (proveedor.get("services") or [])[:2],
                    }
                    for proveedor in proveedores[:5]
                ]
                self.logger.info(
                    "📊 Candidatos previos a validación IA para '%s' en %s: %s",
                    profesion,
                    ciudad,
                    resumen_scores,
                )

            # Si no hay proveedores, retornar vacío
            if not proveedores:
                return {"ok": True, "providers": [], "total": 0}

            candidatos_a_validar = self._priorizar_candidatos_para_validacion(
                proveedores
            )

            # NUEVO: Validar con IA antes de devolver
            proveedores_validados = await self.validador_ia.validar_proveedores(
                necesidad_usuario=profesion,
                descripcion_problema=descripcion_problema or profesion,
                proveedores=candidatos_a_validar,
                request_domain_code=domain_code,
                request_category_name=category_name,
                request_domain=domain,
                request_category=category,
                search_profile=profile,
            )
            proveedores_rankeados = self._rankear_proveedores(
                proveedores=proveedores_validados,
                necesidad_usuario=profesion,
                descripcion_problema=descripcion_problema or profesion,
                domain=domain,
                domain_code=domain_code,
                category=category,
                category_name=category_name,
            )

            self.logger.info(
                f"🎯 Validación final: {len(proveedores_rankeados)}/{total} "
                f"proveedores pasaron validación IA"
            )

            return {
                "ok": True,
                "providers": proveedores_rankeados,
                "total": len(proveedores_rankeados),
                "search_scope": "local",
            }

        except Exception as exc:
            self.logger.error(f"❌ Error en búsqueda: {exc}")
            return {"ok": False, "providers": [], "total": 0}

    @staticmethod
    def _build_canonical_query(
        *,
        profesion: str,
        service_summary: Optional[str] = None,
        descripcion_problema: Optional[str] = None,
        domain: Optional[str] = None,
        domain_code: Optional[str] = None,
        category: Optional[str] = None,
        category_name: Optional[str] = None,
    ) -> str:
        """Construye la consulta canónica priorizando servicio y taxonomía."""
        query_parts = [
            str(service_summary or profesion or "").strip(),
            str(domain_code or domain or "").strip(),
            str(category_name or category or "").strip(),
        ]
        deduped_parts = []
        seen = set()
        for part in query_parts:
            normalized = part.lower().strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped_parts.append(part)

        if deduped_parts:
            return " ".join(deduped_parts)

        fallback = str(descripcion_problema or "").strip()
        return fallback or str(profesion or "").strip()

    def _priorizar_candidatos_para_validacion(
        self, proveedores: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """Reduce el universo a validar priorizando compatibilidad semántica."""
        if not proveedores:
            return []

        candidatos = sorted(
            proveedores,
            key=lambda proveedor: (
                float(proveedor.get("semantic_alignment_score") or 0.0),
                float(proveedor.get("retrieval_score") or 0.0),
                float(proveedor.get("similarity_score") or 0.0),
                float(proveedor.get("classification_confidence") or 0.0),
                float(proveedor.get("rating") or 0.0),
            ),
            reverse=True,
        )

        limite = max(1, int(configuracion.search_validation_limit or 0))
        return candidatos[: min(len(candidatos), limite)]

    def _rankear_proveedores(
        self,
        *,
        proveedores: list[Dict[str, Any]],
        necesidad_usuario: str,
        descripcion_problema: str,
        domain: Optional[str] = None,
        domain_code: Optional[str] = None,
        category: Optional[str] = None,
        category_name: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """Aplica un ranking híbrido y deja trazabilidad humana en los resultados."""
        query_text = " ".join(
            part.strip()
            for part in [
                necesidad_usuario,
                descripcion_problema,
                domain,
                domain_code,
                category,
                category_name,
            ]
            if str(part or "").strip()
        ).lower()
        query_tokens = {token for token in query_text.split() if len(token) >= 4}
        rankeados: list[Dict[str, Any]] = []
        for proveedor in proveedores:
            similarity = float(proveedor.get("similarity_score") or 0.0)
            retrieval = float(proveedor.get("retrieval_score") or similarity)
            validation = float(proveedor.get("validation_confidence") or 0.0)
            rating = max(0.0, min(1.0, float(proveedor.get("rating") or 0.0) / 5.0))
            metadata_terms = " ".join(
                str(proveedor.get(field) or "").lower()
                for field in (
                    "domain_code",
                    "category_name",
                    "matched_service_name",
                    "matched_service_summary",
                )
            )
            metadata_tokens = {
                token for token in metadata_terms.split() if len(token) >= 4
            }
            metadata_match = (
                len(query_tokens.intersection(metadata_tokens)) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            ranking_score = max(
                0.0,
                min(
                    1.0,
                    retrieval * 0.35
                    + similarity * 0.20
                    + validation * 0.25
                    + metadata_match * 0.10
                    + rating * 0.05
                ),
            )
            proveedor_rankeado = dict(proveedor)
            proveedor_rankeado["ranking_score"] = ranking_score
            proveedor_rankeado["ranking_explain"] = {
                "retrieval_score": round(retrieval, 4),
                "similarity_score": round(similarity, 4),
                "validation_confidence": round(validation, 4),
                "metadata_match": round(metadata_match, 4),
                "rating_score": round(rating, 4),
            }
            rankeados.append(proveedor_rankeado)

        rankeados.sort(
            key=lambda proveedor: (
                float(proveedor.get("ranking_score") or 0.0),
                float(proveedor.get("validation_confidence") or 0.0),
                float(proveedor.get("similarity_score") or 0.0),
            ),
            reverse=True,
        )
        return rankeados
