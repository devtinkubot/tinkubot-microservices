import asyncio
import sys
import types

from models.proveedores import SolicitudCreacionProveedor
from services.registro.registro_proveedor import (
    insertar_servicios_proveedor,
    registrar_proveedor_en_base_datos,
)


def test_registro_inicial_persiste_servicios_normalizados_sin_taxonomia_runtime(monkeypatch):
    captured = {}

    class _Resultado:
        def __init__(self, data):
            self.data = data
            self.error = None

    class _Query:
        def upsert(self, payload, on_conflict=None):
            captured["upsert_payload"] = payload
            captured["upsert_on_conflict"] = on_conflict
            return self

        def execute(self):
            return _Resultado(
                [
                    {
                        "id": "prov-1",
                        "phone": "593959091325@s.whatsapp.net",
                        "full_name": "Diego",
                        "city": "quito",
                        "experience_years": 3,
                        "rating": 5.0,
                        "verified": False,
                        "has_consent": True,
                        "social_media_url": None,
                        "social_media_type": None,
                    }
                ]
            )

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "providers"
            return _Query()

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    async def _fake_insertar_servicios_proveedor(
        *, supabase, proveedor_id, servicios, servicio_embeddings, tiempo_espera=5.0
    ):
        captured["proveedor_id"] = proveedor_id
        captured["servicios"] = servicios
        captured["servicio_embeddings"] = servicio_embeddings
        captured["tiempo_espera"] = tiempo_espera
        return {
            "inserted_rows": [],
            "requested_count": len(servicios),
            "inserted_count": len(servicios),
            "failed_services": [],
        }

    monkeypatch.setattr("services.registro.registro_proveedor.run_supabase", _fake_run_supabase)
    monkeypatch.setattr(
        "services.registro.registro_proveedor.insertar_servicios_proveedor",
        _fake_insertar_servicios_proveedor,
    )

    flows_sesion_stub = types.ModuleType("flows.sesion")

    async def _fake_cachear_perfil_proveedor(_telefono, _perfil):
        return None

    async def _fake_limpiar_marca_perfil_eliminado(_telefono):
        return None

    flows_sesion_stub.cachear_perfil_proveedor = _fake_cachear_perfil_proveedor
    flows_sesion_stub.limpiar_marca_perfil_eliminado = (
        _fake_limpiar_marca_perfil_eliminado
    )
    sys.modules["flows.sesion"] = flows_sesion_stub

    solicitud = SolicitudCreacionProveedor(
        phone="593959091325@s.whatsapp.net",
        real_phone="593959091325",
        full_name="diego",
        city="Quito",
        services_list=["laboralista"],
        experience_years=3,
        has_consent=True,
        social_media_url=None,
        social_media_type=None,
    )

    resultado = asyncio.run(
        registrar_proveedor_en_base_datos(
            _SupabaseStub(),
            solicitud,
            servicio_embeddings=object(),
        )
    )

    assert resultado is not None
    assert captured["servicios"] == [
        {
            "raw_service_text": "laboralista",
            "service_name": "Laboralista",
            "service_summary": "",
        }
    ]
    assert captured["proveedor_id"] == "prov-1"


def test_insertar_servicios_envia_a_revision_si_el_dominio_no_pertenece_al_catalogo(
    monkeypatch,
):
    captured = {}

    class _ProviderServicesQuery:
        def insert(self, _payload):
            raise AssertionError("No debe insertar servicios sin dominio resuelto")

    class _SupabaseStub:
        def table(self, table_name):
            assert table_name == "provider_services"
            return _ProviderServicesQuery()

    async def _fake_clasificar_servicios_livianos(**_kwargs):
        return [
            {
                "normalized_service": "Instalación de paneles solares",
                "domain_code": "energia_renovable",
                "resolved_domain_code": None,
                "domain_resolution_status": "catalog_review_required",
                "category_name": "instalación de paneles solares",
                "proposed_category_name": "instalación de paneles solares",
                "service_summary": "Instalo paneles solares para hogares y negocios.",
                "proposed_service_summary": "Instalo paneles solares para hogares y negocios.",
                "classification_confidence": 0.91,
            }
        ]

    async def _fake_registrar_revision_catalogo_servicio(**kwargs):
        captured.update(kwargs)
        return {"id": "review-1"}

    monkeypatch.setattr(
        "services.registro.registro_proveedor.clasificar_servicios_livianos",
        _fake_clasificar_servicios_livianos,
    )
    monkeypatch.setattr(
        "services.registro.registro_proveedor.registrar_revision_catalogo_servicio",
        _fake_registrar_revision_catalogo_servicio,
    )

    resultado = asyncio.run(
        insertar_servicios_proveedor(
            _SupabaseStub(),
            "prov-1",
            [
                {
                    "raw_service_text": "instalacion de paneles solares",
                    "service_name": "Instalación de paneles solares",
                    "service_summary": "",
                }
            ],
            servicio_embeddings=None,
        )
    )

    assert resultado["inserted_count"] == 0
    assert resultado["failed_services"] == [
        {
            "service": "Instalación de paneles solares",
            "error": "catalog_review_required",
        }
    ]
    assert captured["provider_id"] == "prov-1"
    assert captured["suggested_domain_code"] == "energia_renovable"
