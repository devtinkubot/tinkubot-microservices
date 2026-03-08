import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.constructores.construidor_servicios import construir_menu_servicios
from services.sesion_proveedor import sincronizar_flujo_con_perfil


def test_menu_servicios_muestra_pendientes_genericos_separados():
    mensaje = construir_menu_servicios(
        ["desarrollo de software", "cableado estructurado"],
        5,
        servicios_pendientes_genericos=["transporte carga", "asesoria legal"],
    )

    assert "Gestión de Servicios" in mensaje
    assert "Gestionar servicios activos" in mensaje
    assert "Gestionar servicios pendientes" in mensaje
    assert "Activos: 2" in mensaje
    assert "Pendientes por precisar: 2" in mensaje


def test_sincronizar_flujo_con_perfil_carga_revision_generica():
    flujo = {}
    perfil = {
        "id": "prov-1",
        "services_list": ["plomeria"],
        "service_review_required": True,
        "generic_services_removed": ["transporte carga", "asesoria legal"],
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["service_review_required"] is True
    assert flujo["generic_services_removed"] == [
        "transporte carga",
        "asesoria legal",
    ]
