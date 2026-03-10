import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.gestores_estados.gestor_servicios as modulo_gestor_servicios  # noqa: E402
from flows.gestores_estados.gestor_confirmacion_servicios import (  # noqa: E402
    manejar_accion_edicion_servicios_registro,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
)
from flows.gestores_estados.gestor_espera_especialidad import (  # noqa: E402
    manejar_espera_especialidad,
)
from flows.gestores_estados.gestor_espera_nombre import (  # noqa: E402
    manejar_espera_nombre,
)
from flows.gestores_estados.gestor_servicios import (  # noqa: E402
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
)
from infrastructure.openai import (  # noqa: E402
    transformador_servicios as modulo_transformador,
)
from templates.registro import (  # noqa: E402
    mensaje_correccion_servicios,
    preguntar_servicios_registro,
    solicitar_foto_dni_frontal,
)


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


def test_prompt_transformador_prioriza_detalle_y_evita_paraguas():
    prompt = modulo_transformador._crear_prompt_sistema()

    assert "SI HAY DETALLE, NO LO GENERALICES" in prompt
    assert "rebaja de pensión alimenticia" in prompt
    assert "destape de cañerías en lavamanos" in prompt
    assert "configuración de redes e internet" in prompt
    assert 'NO debe convertirse en "instalación de internet"' in prompt


def test_prompt_servicios_registro_usa_ejemplos_especificos():
    mensaje = preguntar_servicios_registro()

    assert "primer servicio" in mensaje
    assert "servicio y la especialidad o área exacta" in mensaje
    assert "asesoría en ley laboral" in mensaje
    assert "defensa en demandas laborales" in mensaje
    assert "destape de cañerías" in mensaje
    assert "reparación de fugas" in mensaje
    assert "desarrollo web" in mensaje


def test_espera_nombre_salta_directo_a_documentos():
    flujo = {"state": "awaiting_name"}
    respuesta = manejar_espera_nombre(
        flujo=flujo,
        texto_mensaje="Diego Unkuch",
    )

    assert flujo["state"] == "awaiting_dni_front_photo"
    assert respuesta["messages"][0]["response"] == solicitar_foto_dni_frontal()


def test_mensaje_correccion_servicios_refuerza_especificidad():
    mensaje = mensaje_correccion_servicios()

    assert "servicio y la especialidad o área exacta" in mensaje
    assert "asesoría en ley laboral" in mensaje
    assert "defensa en demandas laborales" in mensaje
    assert "destape de cañerías" in mensaje
    assert "desarrollo web" in mensaje


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


def test_espera_especialidad_agrega_servicio_y_pregunta_si_quiere_otro(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorOK,
    )
    flujo = {"state": "awaiting_specialty"}

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="desarrollo web",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_add_another_service"
    assert flujo["servicios_temporales"] == ["servicio normalizado"]
    assert "¿Quieres agregar otro servicio?" in respuesta["messages"][0]["response"]


def test_decision_agregar_otro_no_pasa_a_resumen_final():
    flujo = {
        "state": "awaiting_add_another_service",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_decision_agregar_otro_servicio(
            flujo=flujo,
            texto_mensaje="2",
        )
    )

    assert flujo["state"] == "awaiting_services_confirmation"
    assert "Resumen de servicios registrados" in respuesta["messages"][0]["response"]


def test_confirmacion_agregar_servicios_re_normaliza_correccion_manual(monkeypatch):
    monkeypatch.setattr(
        modulo_gestor_servicios, "TransformadorServicios", _TransformadorOK
    )
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


def test_confirmacion_servicios_acepta_resumen_y_pasa_a_experiencia():
    flujo = {
        "state": "awaiting_services_confirmation",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_experience"
    assert flujo["specialty"] == "desarrollo web, cableado estructurado"
    assert (
        "¿Cuántos años de experiencia tienes?" in respuesta["messages"][0]["response"]
    )


def test_confirmacion_servicios_abre_menu_edicion():
    flujo = {
        "state": "awaiting_services_confirmation",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="2",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_services_edit_action"
    assert "¿Qué deseas corregir?" in respuesta["messages"][1]["response"]


def test_reemplazo_servicio_en_edicion(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorOK,
    )
    flujo = {
        "state": "awaiting_services_edit_action",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta_select = asyncio.run(
        manejar_accion_edicion_servicios_registro(flujo, "1")
    )
    assert flujo["state"] == "awaiting_services_edit_replace_select"
    assert "reemplazar" in respuesta_select["messages"][1]["response"].lower()

    respuesta_indice = asyncio.run(
        manejar_seleccion_reemplazo_servicio_registro(flujo, "2")
    )
    assert flujo["state"] == "awaiting_services_edit_replace_input"
    assert "servicio 2" in respuesta_indice["messages"][0]["response"].lower()

    respuesta_reemplazo = asyncio.run(
        manejar_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje="abogado para rebaja de pensión alimenticia",
            cliente_openai=object(),
        )
    )
    assert flujo["state"] == "awaiting_services_confirmation"
    assert flujo["servicios_temporales"] == [
        "desarrollo web",
        "asesoria rebaja pension alimenticia",
    ]
    assert "Servicio actualizado" in respuesta_reemplazo["messages"][0]["response"]


def test_eliminacion_servicio_en_edicion():
    flujo = {
        "state": "awaiting_services_edit_delete_select",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_eliminacion_servicio_registro(
            flujo=flujo,
            texto_mensaje="1",
        )
    )

    assert flujo["state"] == "awaiting_services_confirmation"
    assert flujo["servicios_temporales"] == ["cableado estructurado"]
    assert "Servicio eliminado" in respuesta["messages"][0]["response"]


def test_agregar_servicios_bloquea_servicio_generico_critico(monkeypatch):
    class _TransformadorGenerico:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
            return ["transporte de mercancías"]

    monkeypatch.setattr(
        modulo_gestor_servicios, "TransformadorServicios", _TransformadorGenerico
    )

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo={"state": "awaiting_service_add", "services": []},
            proveedor_id="prov-1",
            texto_mensaje="transporte de mercancías",
            cliente_openai=object(),
        )
    )

    assert "terrestre, marítimo o aéreo" in respuesta["messages"][0]["response"]
