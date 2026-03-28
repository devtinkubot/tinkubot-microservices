import asyncio

from services.maintenance.revision_catalogo import (
    eliminar_revisiones_catalogo_asociadas_servicio,
    generar_sugerencia_revision_catalogo_servicio,
    registrar_revision_catalogo_servicio,
)


def test_registrar_revision_catalogo_servicio_actualiza_review_pendiente(monkeypatch):
    captured = {}

    class _Resultado:
        def __init__(self, data):
            self.data = data

    class _Query:
        def select(self, _fields):
            return self

        def match(self, payload):
            captured["match"] = payload
            return self

        def limit(self, _count):
            return self

        def update(self, payload):
            captured["update_payload"] = payload
            return self

        def insert(self, payload):
            captured["insert_payload"] = payload
            return self

        def delete(self):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            if captured.get("label") == "provider_service_catalog_reviews.find_pending_duplicate":
                return _Resultado([{"id": "review-1"}])
            if captured.get("label") == "provider_service_catalog_reviews.update_pending":
                return _Resultado(
                    [
                        {
                            "id": "review-1",
                            **captured.get("update_payload", {}),
                        }
                    ]
                )
            raise AssertionError(f"Label inesperado: {captured.get('label')}")

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "provider_service_catalog_reviews"
            return _Query()

    async def _fake_run_supabase(operation, **kwargs):
        captured["label"] = kwargs.get("label")
        return operation()

    monkeypatch.setattr(
        "services.maintenance.revision_catalogo.run_supabase",
        _fake_run_supabase,
    )

    resultado = asyncio.run(
        registrar_revision_catalogo_servicio(
            supabase=_SupabaseStub(),
            provider_id="prov-1",
            raw_service_text="gestion de proyectos tics",
            service_name="Gestión de proyectos TIC",
            suggested_domain_code=None,
            proposed_category_name=None,
            proposed_service_summary="Gestión de proyectos relacionados con tecnologías de la información.",
            review_reason="catalog_review_required",
            source="provider_onboarding",
        )
    )

    assert resultado["id"] == "review-1"
    assert captured["match"]["provider_id"] == "prov-1"
    assert captured["match"]["service_name_normalized"] == "gestion de proyectos tic"
    assert captured["update_payload"]["review_reason"] == "catalog_review_required"


def test_registrar_revision_catalogo_servicio_sanea_null_like_values(monkeypatch):
    captured = {}

    class _Resultado:
        def __init__(self, data):
            self.data = data

    class _Query:
        def select(self, _fields):
            return self

        def match(self, payload):
            captured["match"] = payload
            return self

        def limit(self, _count):
            return self

        def update(self, payload):
            captured["update_payload"] = payload
            return self

        def insert(self, payload):
            captured["insert_payload"] = payload
            return self

        def execute(self):
            return _Resultado([])

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "provider_service_catalog_reviews"
            return _Query()

    async def _fake_run_supabase(operation, **kwargs):
        captured["label"] = kwargs.get("label")
        return operation()

    monkeypatch.setattr(
        "services.maintenance.revision_catalogo.run_supabase",
        _fake_run_supabase,
    )

    resultado = asyncio.run(
        registrar_revision_catalogo_servicio(
            supabase=_SupabaseStub(),
            provider_id="prov-1",
            raw_service_text="Gestion de proyectos tics",
            service_name="Gestion de proyectos tics",
            suggested_domain_code="null",
            proposed_category_name="null",
            proposed_service_summary="null",
            review_reason="null",
            source="provider_onboarding",
        )
    )

    assert resultado is None or "id" not in resultado
    assert captured["insert_payload"]["suggested_domain_code"] is None
    assert captured["insert_payload"]["proposed_category_name"] is None
    assert captured["insert_payload"]["proposed_service_summary"] is None
    assert captured["insert_payload"]["review_reason"] == "catalog_review_required"


def test_generar_sugerencia_revision_catalogo_servicio_usa_salida_estructurada():
    class _Choice:
        def __init__(self, content):
            self.message = type("Msg", (), {"content": content})()

    class _Resp:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _Completions:
        async def create(self, **kwargs):
            self.kwargs = kwargs
            return _Resp(
                '{"suggested_domain_code":"tecnologia",'
                '"proposed_category_name":"Servicios tecnológicos",'
                '"proposed_service_summary":"Gestión de proyectos tecnológicos con foco en IA.",'
                '"review_reason":"best_effort_catalog_suggestion",'
                '"confidence":0.86}'
            )

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _OpenAIStub:
        def __init__(self):
            self.chat = _Chat()

    suggestion = asyncio.run(
        generar_sugerencia_revision_catalogo_servicio(
            cliente_openai=_OpenAIStub(),
            raw_service_text="Gestion de proyectos de TICs",
            service_name="Gestión de proyectos TIC",
            dominios_catalogo=[
                {
                    "code": "tecnologia",
                    "display_name": "Tecnología",
                    "description": "Servicios de software y soporte",
                }
            ],
        )
    )

    assert suggestion["suggested_domain_code"] == "tecnologia"
    assert suggestion["proposed_category_name"] == "Servicios tecnológicos"
    assert "IA" in suggestion["proposed_service_summary"]


def test_eliminar_revisiones_catalogo_asociadas_servicio(monkeypatch):
    captured = {}

    class _Resultado:
        def __init__(self, data):
            self.data = data

    class _Query:
        def __init__(self):
            self.filters = {}

        def delete(self):
            return self

        def eq(self, field, value):
            self.filters[field] = value
            return self

        def execute(self):
            captured["filters"] = dict(self.filters)
            return _Resultado([{"id": "review-1"}])

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "provider_service_catalog_reviews"
            return _Query()

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    monkeypatch.setattr(
        "services.maintenance.revision_catalogo.run_supabase",
        _fake_run_supabase,
    )

    eliminadas = asyncio.run(
        eliminar_revisiones_catalogo_asociadas_servicio(
            supabase=_SupabaseStub(),
            provider_id="prov-1",
            published_provider_service_id="service-1",
        )
    )

    assert eliminadas == 1
    assert captured["filters"]["provider_id"] == "prov-1"
    assert captured["filters"]["published_provider_service_id"] == "service-1"
