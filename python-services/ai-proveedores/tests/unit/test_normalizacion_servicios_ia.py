import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.gestores_estados.gestor_confirmacion_servicios import (  # noqa: E402
    manejar_confirmacion_servicios,
)
from flows.gestores_estados.gestor_espera_especialidad import (  # noqa: E402
    manejar_espera_especialidad,
)
import flows.gestores_estados.gestor_servicios as modulo_gestor_servicios  # noqa: E402
from flows.gestores_estados.gestor_servicios import (  # noqa: E402
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
)
from infrastructure.openai import transformador_servicios as modulo_transformador  # noqa: E402


class _TransformadorOK:
    def __init__(self, cliente_openai, modelo=None):
        self.cliente_openai = cliente_openai
        self.modelo = modelo

    async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
        if "rebaja de pensión alimenticia" in entrada_usuario:
            return ["asesoría para rebaja de pensión alimenticia"]
        if "destapar lavamanos" in entrada_usuario:
            return ["destape de cañerías en lavamanos"]
        return ["servicio normalizado"]


class _TransformadorVacio:
    def __init__(self, cliente_openai, modelo=None):
        self.cliente_openai = cliente_openai
        self.modelo = modelo

    async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
        return None


def test_prompt_transformador_prioriza_detalle_y_evita_paraguas():
    prompt = modulo_transformador._crear_prompt_sistema()

    assert "SI HAY DETALLE, NO LO GENERALICES" in prompt
    assert "rebaja de pensión alimenticia" in prompt
    assert "destape de cañerías en lavamanos" in prompt
    assert "configuración de redes e internet" in prompt
    assert "NO debe convertirse en \"instalación de internet\"" in prompt


def test_normalizador_corrige_frase_poco_natural():
    servicios = modulo_transformador._normalizar_y_limitar_servicios(
        ["desarrollo software"],
        5,
        entrada_usuario="Desarrollo de software",
    )

    assert servicios == ["desarrollo de software"]


def test_normalizador_evitar_sobre_expansion_y_cambio_semantico():
    servicios = modulo_transformador._normalizar_y_limitar_servicios(
        [
            "desarrollo software",
            "configuracion redes",
            "instalacion internet",
            "cableado estructurado",
        ],
        10,
        entrada_usuario=(
            "Desarrollo de software, configuracion de redes e internet, "
            "servicios de cableado estructurado"
        ),
    )

    assert servicios == [
        "desarrollo de software",
        "configuracion de redes e internet",
        "cableado estructurado",
    ]


def test_confirmacion_registro_re_normaliza_correccion_manual(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorOK,
    )
    flujo = {
        "state": "awaiting_services_confirmation",
        "servicios_temporales": ["asesoría legal"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="abogado para rebaja de pensión alimenticia",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_services_confirmation"
    assert flujo["servicios_temporales"] == [
        "asesoría para rebaja de pensión alimenticia"
    ]
    assert "specialty" not in flujo
    assert (
        "asesoría para rebaja de pensión alimenticia"
        in respuesta["messages"][0]["response"]
    )


def test_confirmacion_registro_fallback_a_lista_manual_si_ia_falla(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorVacio,
    )
    flujo = {
        "state": "awaiting_services_confirmation",
        "servicios_temporales": ["servicio anterior"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="reparación de fugas, destape de cañerías",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_services_confirmation"
    assert flujo["servicios_temporales"] == [
        "reparación de fugas",
        "destape de cañerías",
    ]
    assert "reparación de fugas" in respuesta["messages"][0]["response"]
    assert "destape de cañerías" in respuesta["messages"][0]["response"]


def test_confirmacion_agregar_servicios_re_normaliza_correccion_manual(monkeypatch):
    monkeypatch.setattr(modulo_gestor_servicios, "TransformadorServicios", _TransformadorOK)
    flujo = {
        "state": "awaiting_service_add_confirmation",
        "services": ["Pintura interior"],
        "service_add_temporales": ["plomería"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-123",
            texto_mensaje="plomero para destapar lavamanos",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_service_add_confirmation"
    assert flujo["service_add_temporales"] == ["destape canerias lavamanos"]
    assert "destape canerias lavamanos" in respuesta["messages"][0]["response"]


def test_espera_especialidad_bloquea_servicio_generico_critico(monkeypatch):
    class _TransformadorGenerico:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
            return ["asesoría legal"]

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorGenerico,
    )

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo={"state": "awaiting_specialty"},
            texto_mensaje="asesoria legal",
            cliente_openai=object(),
        )
    )

    assert "área legal exacta" in respuesta["messages"][0]["response"]


def test_agregar_servicios_bloquea_servicio_generico_critico(monkeypatch):
    class _TransformadorGenerico:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
            return ["transporte de mercancías"]

    monkeypatch.setattr(modulo_gestor_servicios, "TransformadorServicios", _TransformadorGenerico)

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo={"state": "awaiting_service_add", "services": []},
            proveedor_id="prov-1",
            texto_mensaje="transporte de mercancías",
            cliente_openai=object(),
        )
    )

    assert "terrestre, marítimo o aéreo" in respuesta["messages"][0]["response"]
