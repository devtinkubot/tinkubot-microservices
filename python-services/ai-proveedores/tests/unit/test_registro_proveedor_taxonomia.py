import asyncio
import sys
import types

from models.proveedores import SolicitudCreacionProveedor
from services.registro.registro_proveedor import (
    insertar_servicios_proveedor,
    registrar_proveedor_en_base_datos,
)
from services.registro.normalizacion import normalizar_datos_proveedor


def test_registro_inicial_persiste_servicios_normalizados_sin_taxonomia_runtime(
    monkeypatch,
):
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
                        "experience_range": "3 a 5 años",
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

    monkeypatch.setattr(
        "services.registro.registro_proveedor.run_supabase", _fake_run_supabase
    )
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
        document_first_names="Diego",
        document_last_names="Unkuch Gonzalez",
        document_id_number="0912345678",
    )

    resultado = asyncio.run(
        registrar_proveedor_en_base_datos(
            _SupabaseStub(),
            solicitud,
            servicio_embeddings=object(),
        )
    )

    assert resultado is not None
    assert captured["upsert_payload"]["document_first_names"] == "Diego"
    assert captured["upsert_payload"]["document_last_names"] == "Unkuch Gonzalez"
    assert captured["upsert_payload"]["document_id_number"] == "0912345678"
    assert captured["upsert_payload"]["experience_range"] == "3 a 5 años"
    assert captured["servicios"] == [
        {
            "raw_service_text": "laboralista",
            "service_name": "Laboralista",
            "service_summary": "",
        }
    ]
    assert captured["proveedor_id"] == "prov-1"
    assert resultado["document_first_names"] == "Diego"
    assert resultado["document_last_names"] == "Unkuch Gonzalez"
    assert resultado["document_id_number"] == "0912345678"
    assert resultado["experience_range"] == "3 a 5 años"


def test_normalizar_datos_proveedor_incluye_identidad_documental():
    solicitud = SolicitudCreacionProveedor(
        phone="593959091325@s.whatsapp.net",
        real_phone="593959091325",
        full_name="diego",
        city="Quito",
        services_list=[],
        experience_years=1,
        has_consent=True,
        document_first_names="Diego",
        document_last_names="Unkuch Gonzalez",
        document_id_number="0912345678",
    )

    normalizado = normalizar_datos_proveedor(solicitud)

    assert normalizado["document_first_names"] == "Diego"
    assert normalizado["document_last_names"] == "Unkuch Gonzalez"
    assert normalizado["document_id_number"] == "0912345678"
    assert normalizado["experience_range"] == "1 a 3 años"


def test_insertar_servicios_persiste_taxonomia_sugerida_sin_revision(
    monkeypatch,
):
    captured = {}

    class _Resultado:
        def __init__(self, data):
            self.data = data
            self.error = None

    class _ProviderServicesQuery:
        def insert(self, payload):
            captured["payload"] = payload
            return self

        def execute(self):
            return _Resultado(
                [
                    {
                        "id": "service-1",
                        "provider_id": "prov-1",
                        **captured.get("payload", {}),
                    }
                ]
            )

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
                "service_summary": (
                    "Instalo paneles solares para hogares " "y negocios."
                ),
                "proposed_service_summary": (
                    "Instalo paneles solares para hogares " "y negocios."
                ),
                "classification_confidence": 0.91,
            }
        ]

    monkeypatch.setattr(
        "services.registro.registro_proveedor.clasificar_servicios_livianos",
        _fake_clasificar_servicios_livianos,
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

    assert resultado["inserted_count"] == 1
    assert resultado["failed_services"] == []
    assert captured["payload"]["provider_id"] == "prov-1"
    assert captured["payload"]["domain_code"] == "energia_renovable"
    assert captured["payload"]["category_name"] == "instalación de paneles solares"
