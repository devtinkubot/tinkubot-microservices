import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.constructores.construidor_servicios import (  # noqa: E402
    construir_menu_servicios,
)
from services.sesion_proveedor import sincronizar_flujo_con_perfil  # noqa: E402


def test_menu_servicios_muestra_lista_unificada():
    mensaje = construir_menu_servicios(
        ["desarrollo de software", "cableado estructurado"],
        5,
    )

    assert "Gestión de Servicios" in mensaje
    assert "Agregar servicio" in mensaje
    assert "Eliminar servicio" in mensaje
    assert "Registrados: 2" in mensaje
    assert "Servicios registrados" in mensaje


def test_sincronizar_flujo_con_perfil_fusiona_servicios_legados():
    flujo = {}
    perfil = {
        "id": "prov-1",
        "services_list": ["plomeria"],
        "generic_services_removed": ["transporte carga", "asesoria legal"],
    }

    sincronizar_flujo_con_perfil(flujo, perfil)

    assert flujo["services"] == [
        "plomeria",
        "transporte carga",
        "asesoria legal",
    ]
