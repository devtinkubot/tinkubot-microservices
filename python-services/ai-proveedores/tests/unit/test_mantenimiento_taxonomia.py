import asyncio

from services.servicios_proveedor.mantenimiento_taxonomia import (
    planificar_mantenimiento_taxonomia,
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

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def _match(self, row):
        for field, value in self.filters:
            if str(row.get(field)) != str(value):
                return False
        return True

    def execute(self):
        rows = self.tables.setdefault(self.table_name, [])
        if self.mode == "select":
            return _Resultado([dict(row) for row in rows if self._match(row)])

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


def test_planificar_mantenimiento_taxonomia_crea_borradores_y_supersede_hermanos(
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
        "service_precision_rules": [
            {
                "id": "rule-1",
                "domain_id": "dom-legal",
                "required_dimensions": ["area"],
                "generic_examples": ["asesoría"],
                "sufficient_examples": ["asesoría laboral"],
                "client_prompt_template": "c",
                "provider_prompt_template": "p",
            }
        ],
        "service_taxonomy_suggestions": [
            {
                "id": "sug-1",
                "source_channel": "provider",
                "source_text": "asesoría laboral",
                "normalized_text": "asesoria laboral",
                "context_excerpt": "asesoría laboral",
                "proposed_domain_code": "legal",
                "proposed_service_candidate": "asesoría laboral",
                "proposed_canonical_name": "asesoría laboral",
                "missing_dimensions": ["tipo de trámite"],
                "proposal_type": "alias",
                "confidence_score": 0.92,
                "evidence_json": {"alias_match": {"alias_text": "asesoría laboral"}},
                "review_status": "pending",
                "cluster_key": "cluster-a",
                "occurrence_count": 5,
                "first_seen_at": "2026-03-09T00:00:00+00:00",
                "last_seen_at": "2026-03-10T00:00:00+00:00",
                "created_at": "2026-03-09T00:00:00+00:00",
                "updated_at": "2026-03-10T00:00:00+00:00",
            },
            {
                "id": "sug-2",
                "source_channel": "provider",
                "source_text": "asesoría para contratos",
                "normalized_text": "asesoria para contratos",
                "context_excerpt": "asesoría para contratos",
                "proposed_domain_code": "legal",
                "proposed_service_candidate": "asesoría para contratos",
                "proposed_canonical_name": "asesoría para contratos",
                "missing_dimensions": ["área exacta"],
                "proposal_type": "alias",
                "confidence_score": 0.55,
                "evidence_json": {},
                "review_status": "pending",
                "cluster_key": "cluster-a",
                "occurrence_count": 2,
                "first_seen_at": "2026-03-08T00:00:00+00:00",
                "last_seen_at": "2026-03-08T10:00:00+00:00",
                "created_at": "2026-03-08T00:00:00+00:00",
                "updated_at": "2026-03-08T10:00:00+00:00",
            },
            {
                "id": "sug-3",
                "source_channel": "provider",
                "source_text": "revisión de contratos",
                "normalized_text": "revision de contratos",
                "context_excerpt": "revisión de contratos",
                "proposed_domain_code": "legal",
                "proposed_service_candidate": "revisión de contratos",
                "proposed_canonical_name": "revisión de contratos",
                "missing_dimensions": ["documentación"],
                "proposal_type": "rule_update",
                "confidence_score": 0.81,
                "evidence_json": {},
                "review_status": "enriched",
                "cluster_key": "cluster-b",
                "occurrence_count": 1,
                "first_seen_at": "2026-03-11T00:00:00+00:00",
                "last_seen_at": "2026-03-11T12:00:00+00:00",
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T12:00:00+00:00",
            },
        ],
        "service_taxonomy_change_queue": [],
    }
    supabase = _SupabaseStub(tables)

    monkeypatch.setattr(
        "services.servicios_proveedor.mantenimiento_taxonomia.run_supabase",
        _fake_run_supabase,
    )

    resultado = asyncio.run(
        planificar_mantenimiento_taxonomia(
            supabase=supabase,
            cluster_keys=["cluster-a"],
            suggestion_ids=["sug-3"],
            review_notes="Ajuste desde chat",
            reviewer="governance-chat",
        )
    )

    assert resultado["success"] is True
    assert resultado["draftsCreated"] == 2
    assert resultado["supersededSuggestions"] == 1
    assert len(resultado["details"]) == 2

    drafts = tables["service_taxonomy_change_queue"]
    assert len(drafts) == 2
    assert drafts[0]["status"] == "draft"
    assert drafts[0]["approved_by"] == "governance-chat"
    assert drafts[0]["target_domain_code"] == "legal"
    assert drafts[0]["payload_json"]["proposed_rule_update"]["required_dimensions"] == [
        "area",
        "tipo de trámite",
    ]
    assert drafts[1]["action_type"] == "rule_update"
    assert drafts[1]["payload_json"]["proposed_rule_update"]["required_dimensions"] == [
        "area",
        "documentación",
    ]

    statuses = {
        row["id"]: row["review_status"]
        for row in tables["service_taxonomy_suggestions"]
    }
    assert statuses["sug-1"] == "approved"
    assert statuses["sug-2"] == "superseded"
    assert statuses["sug-3"] == "approved"
