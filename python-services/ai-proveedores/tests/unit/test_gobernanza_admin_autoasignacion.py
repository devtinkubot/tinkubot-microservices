import asyncio
import sys
import types

import services.servicios_proveedor.gobernanza_autoasignacion as autoasignacion
from services.servicios_proveedor.gobernanza_autoasignacion import (
    auto_asignar_reviews_gobernanza_pendientes,
)


class _Resultado:
    def __init__(self, data):
        self.data = data
        self.error = None


class _Query:
    def __init__(self, table_name, tables):
        self.table_name = table_name
        self.tables = tables
        self.mode = "select"
        self.payload = None
        self.filters = []
        self._order = None
        self._limit = None

    def select(self, *_args, **_kwargs):
        self.mode = "select"
        return self

    def insert(self, payload):
        self.mode = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.mode = "update"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self._order = (field, bool(desc))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def _match(self, row):
        for field, value in self.filters:
            if str(row.get(field)) != str(value):
                return False
        return True

    def execute(self):
        rows = self.tables.setdefault(self.table_name, [])
        if self.mode == "select":
            resultados = [dict(row) for row in rows if self._match(row)]
            if self._order:
                field, desc = self._order
                resultados.sort(key=lambda row: str(row.get(field) or ""), reverse=desc)
            if self._limit is not None:
                resultados = resultados[: int(self._limit)]
            return _Resultado(resultados)

        if self.mode == "insert":
            row = dict(self.payload or {})
            row.setdefault("id", f"{self.table_name}-{len(rows) + 1}")
            rows.append(row)
            return _Resultado([dict(row)])

        if self.mode == "update":
            updated = []
            for row in rows:
                if self._match(row):
                    row.update(self.payload or {})
                    updated.append(dict(row))
            return _Resultado(updated)

        return _Resultado([])


class _SupabaseStub:
    def __init__(self, tables):
        self.tables = tables

    def table(self, table_name):
        return _Query(table_name, self.tables)


async def _fake_run_supabase(operation, **_kwargs):
    return operation()


def test_auto_asignar_reviews_gobernanza_pendientes_aprueba_claros_y_salta_ambiguos(
    monkeypatch,
):
    tables = {
        "service_domains": [
            {
                "id": "dom-legal",
                "code": "legal",
                "display_name": "Legal",
                "status": "published",
            }
        ],
        "provider_service_catalog_reviews": [
            {
                "id": "review-sugerido",
                "provider_id": "prov-1",
                "raw_service_text": "asesoría laboral",
                "service_name": "Asesoría laboral",
                "suggested_domain_code": "legal",
                "proposed_category_name": "asesoría legal laboral",
                "proposed_service_summary": "Brindo asesoría laboral.",
                "assigned_domain_code": None,
                "assigned_category_name": None,
                "assigned_service_name": None,
                "assigned_service_summary": None,
                "review_reason": "provider_onboarding",
                "review_status": "pending",
                "source": "provider_onboarding",
                "created_at": "2026-03-10T00:00:00+00:00",
                "updated_at": "2026-03-10T00:00:00+00:00",
            },
            {
                "id": "review-clasificado",
                "provider_id": "prov-1",
                "raw_service_text": "asesoría en derecho laboral",
                "service_name": "Asesoría en derecho laboral",
                "suggested_domain_code": "null",
                "proposed_category_name": "null",
                "proposed_service_summary": "null",
                "assigned_domain_code": None,
                "assigned_category_name": None,
                "assigned_service_name": None,
                "assigned_service_summary": None,
                "review_reason": "provider_onboarding",
                "review_status": "pending",
                "source": "provider_onboarding",
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T00:00:00+00:00",
            },
            {
                "id": "review-ambiguo",
                "provider_id": "prov-1",
                "raw_service_text": "hola",
                "service_name": "hola",
                "suggested_domain_code": "null",
                "proposed_category_name": "null",
                "proposed_service_summary": "null",
                "assigned_domain_code": None,
                "assigned_category_name": None,
                "assigned_service_name": None,
                "assigned_service_summary": None,
                "review_reason": "provider_onboarding",
                "review_status": "pending",
                "source": "provider_onboarding",
                "created_at": "2026-03-12T00:00:00+00:00",
                "updated_at": "2026-03-12T00:00:00+00:00",
            },
        ],
        "providers": [
            {
                "id": "prov-1",
                "phone": "593959091325@s.whatsapp.net",
            }
        ],
        "provider_services": [],
    }
    supabase = _SupabaseStub(tables)

    summary_diseno = "Servicio de diseño de modelo de negocio y propuesta de valor."

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        if servicio == "hola":
            return {
                "is_valid_service": False,
                "needs_clarification": False,
                "normalized_service": servicio,
                "domain_resolution_status": "rejected",
                "domain_code": None,
                "resolved_domain_code": None,
                "category_name": None,
                "proposed_category_name": None,
                "service_summary": None,
                "proposed_service_summary": None,
                "confidence": 0.2,
                "reason": "non_service_text",
                "clarification_question": None,
            }
        if "diseño" in servicio:
            return {
                "is_valid_service": True,
                "needs_clarification": False,
                "normalized_service": servicio,
                "domain_resolution_status": "catalog_review_required",
                "domain_code": None,
                "resolved_domain_code": None,
                "category_name": None,
                "proposed_category_name": None,
                "service_summary": summary_diseno,
                "proposed_service_summary": summary_diseno,
                "confidence": 0.93,
                "reason": "heuristic_accept",
                "clarification_question": None,
            }
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "catalog_review_required",
            "domain_code": None,
            "resolved_domain_code": None,
            "category_name": None,
            "proposed_category_name": None,
            "service_summary": "Brindo asesoría en derecho laboral.",
            "proposed_service_summary": "Brindo asesoría en derecho laboral.",
            "confidence": 0.93,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    flows_sesion_stub = types.ModuleType("flows.sesion")

    async def _fake_invalidar_cache_perfil_proveedor(_telefono):
        return None

    flows_sesion_stub.invalidar_cache_perfil_proveedor = (
        _fake_invalidar_cache_perfil_proveedor
    )
    sys.modules["flows.sesion"] = flows_sesion_stub

    monkeypatch.setattr(
        autoasignacion,
        "run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        autoasignacion,
        "validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )

    resultado = asyncio.run(
        auto_asignar_reviews_gobernanza_pendientes(
            supabase=supabase,
            servicio_embeddings=None,
            cliente_openai=object(),
            limit=10,
            reviewer="governance-auto",
            notes="Auto",
        )
    )

    assert resultado["success"] is True
    assert resultado["resolvedReviews"] == 2
    assert resultado["approvedExistingSuggestionReviews"] == 1
    assert resultado["approvedClassifiedReviews"] == 1
    assert resultado["skippedReviews"] == 1
    assert len(resultado["details"]) == 2

    statuses = {
        row["id"]: row["review_status"]
        for row in tables["provider_service_catalog_reviews"]
    }
    assert statuses["review-sugerido"] == "approved_existing_domain"
    assert statuses["review-clasificado"] == "approved_existing_domain"
    assert statuses["review-ambiguo"] == "pending"

    provider_services = tables["provider_services"]
    assert len(provider_services) == 2
    assert provider_services[0]["domain_code"] == "legal"
    assert provider_services[1]["domain_code"] == "legal"
    assert provider_services[1]["category_name"] == "Asesoría en derecho laboral"


def test_auto_asignar_reviews_gobernanza_pendientes_infiere_dominio_desde_texto(
    monkeypatch,
):
    tables = {
        "service_domains": [
            {
                "id": "dom-admin",
                "code": "servicios_administrativos",
                "display_name": "Servicios Administrativos",
                "status": "published",
            }
        ],
        "provider_service_catalog_reviews": [
            {
                "id": "review-importaciones",
                "provider_id": None,
                "raw_service_text": "Gestora de importaciones",
                "service_name": "gestión de importaciones",
                "suggested_domain_code": "null",
                "proposed_category_name": "null",
                "proposed_service_summary": "null",
                "assigned_domain_code": None,
                "assigned_category_name": None,
                "assigned_service_name": None,
                "assigned_service_summary": None,
                "review_reason": (
                    "El servicio es específico y corresponde a una actividad real "
                    "en el ámbito comercial."
                ),
                "review_status": "pending",
                "source": "provider_onboarding",
                "created_at": "2026-03-13T23:46:43.316388+00:00",
                "updated_at": "2026-03-13T23:46:43.316388+00:00",
            }
        ],
        "providers": [
            {
                "id": "prov-1",
                "phone": "593959091325@s.whatsapp.net",
            }
        ],
        "provider_services": [],
    }
    supabase = _SupabaseStub(tables)

    summary_importaciones = (
        "Servicio de gestión para la importación de bienes y productos."
    )

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "catalog_review_required",
            "domain_code": None,
            "resolved_domain_code": None,
            "category_name": None,
            "proposed_category_name": None,
            "service_summary": summary_importaciones,
            "proposed_service_summary": summary_importaciones,
            "confidence": 0.94,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    flows_sesion_stub = types.ModuleType("flows.sesion")

    async def _fake_invalidar_cache_perfil_proveedor(_telefono):
        return None

    flows_sesion_stub.invalidar_cache_perfil_proveedor = (
        _fake_invalidar_cache_perfil_proveedor
    )
    sys.modules["flows.sesion"] = flows_sesion_stub

    monkeypatch.setattr(
        autoasignacion,
        "run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        autoasignacion,
        "validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )

    resultado = asyncio.run(
        auto_asignar_reviews_gobernanza_pendientes(
            supabase=supabase,
            servicio_embeddings=None,
            cliente_openai=object(),
            limit=10,
            reviewer="governance-auto",
            notes="Auto",
        )
    )

    assert resultado["success"] is True
    assert resultado["resolvedReviews"] == 1
    assert resultado["approvedClassifiedReviews"] == 0
    assert resultado["enrichedReviews"] == 1
    assert resultado["skippedReviews"] == 0
    assert resultado["details"][0]["domainCode"] == "servicios_administrativos"
    assert resultado["details"][0]["reviewStatus"] == "enriched"

    review = tables["provider_service_catalog_reviews"][0]
    assert review["review_status"] == "enriched"
    assert review["assigned_domain_code"] == "servicios_administrativos"
    assert review["assigned_category_name"] == "gestión de importaciones"
    assert tables["provider_services"] == []
