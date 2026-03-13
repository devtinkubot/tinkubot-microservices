import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

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
    normalizar_servicio_registro_individual,
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
from services.servicios_proveedor import clasificacion_semantica as modulo_clasificacion  # noqa: E402
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
        return ["desarrollo web"]


def test_prompt_transformador_prioriza_detalle_y_evita_paraguas():
    prompt = modulo_transformador._crear_prompt_sistema()

    assert "SI HAY DETALLE, NO LO GENERALICES" in prompt
    assert "rebaja de pensión alimenticia" in prompt
    assert "destape de cañerías en lavamanos" in prompt
    assert "configuración de redes e internet" in prompt
    assert 'NO debe convertirse en "instalación de internet"' in prompt
    assert 'No elimines conectores útiles como "de", "a", "para", "en"' in prompt


def test_prompt_servicios_registro_usa_ejemplos_especificos():
    mensaje = preguntar_servicios_registro()

    assert "primer servicio" in mensaje
    assert "servicio y la especialidad o área exacta" in mensaje
    assert "asesoría en derecho laboral" in mensaje
    assert "declaración de impuestos para personas naturales" in mensaje
    assert "desarrollo de software a medida" in mensaje
    assert "instalación de cámaras de seguridad" in mensaje
    assert "terapia psicológica" in mensaje
    assert "transporte de carga" in mensaje


def test_espera_nombre_salta_directo_a_documentos():
    flujo = {"state": "awaiting_name"}
    respuesta = asyncio.run(
        manejar_espera_nombre(
            flujo=flujo,
            texto_mensaje="Diego Unkuch",
        )
    )

    assert flujo["state"] == "awaiting_dni_front_photo"
    assert respuesta["messages"][0]["response"] == solicitar_foto_dni_frontal()


def test_mensaje_correccion_servicios_refuerza_especificidad():
    mensaje = mensaje_correccion_servicios()

    assert "servicio y la especialidad o área exacta" in mensaje
    assert "asesoría en derecho laboral" in mensaje
    assert "declaración de impuestos para personas naturales" in mensaje
    assert "desarrollo de software a medida" in mensaje
    assert "instalación de cámaras de seguridad" in mensaje
    assert "terapia psicológica" in mensaje


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
    assert flujo["servicios_temporales"] == ["desarrollo web"]
    assert "¿Quieres agregar otro servicio?" in respuesta["messages"][0]["response"]


def test_normalizacion_servicio_bloquea_catalog_review_required(monkeypatch):
    class _TransformadorPaneles:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
            return ["instalación de paneles solares"]

    captured = {}

    async def _fake_validar_servicio_semanticamente(**_kwargs):
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": "instalación de paneles solares",
            "domain_resolution_status": "catalog_review_required",
            "domain_code": "energia_renovable",
            "resolved_domain_code": None,
            "proposed_category_name": "instalación de paneles solares",
            "proposed_service_summary": "Instalo paneles solares para hogares y negocios.",
            "reason": "catalog_gap_detected",
        }

    async def _fake_registrar_revision_catalogo_servicio(**kwargs):
        captured.update(kwargs)
        return {"id": "review-1"}

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorPaneles,
    )
    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_especialidad.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )
    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_especialidad.registrar_revision_catalogo_servicio",
        _fake_registrar_revision_catalogo_servicio,
    )

    respuesta = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="instalacion de paneles solares",
            cliente_openai=object(),
        )
    )

    assert respuesta["ok"] is False
    assert "todavía no lo podemos clasificar bien" in respuesta["response"]
    assert captured["service_name"] == "instalación de paneles solares"
    assert captured["source"] == "provider_onboarding"


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
    assert "Resumen de servicios principales" in respuesta["messages"][0]["response"]


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
    assert flujo["service_add_temporales"] == ["destape de cañerías en lavamanos"]
    assert "destape de cañerías en lavamanos" in respuesta["messages"][0]["response"]


def test_espera_especialidad_bloquea_servicio_generico_critico(monkeypatch):
    async def _normalizar_stub(**_kwargs):
        return {
            "ok": False,
            "response": "Indica el trámite o área legal exacta con la que trabajas.",
        }

    monkeypatch.setitem(
        manejar_espera_especialidad.__globals__,
        "normalizar_servicio_registro_individual",
        _normalizar_stub,
    )

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo={"state": "awaiting_specialty"},
            texto_mensaje="asesoria legal",
            cliente_openai=object(),
        )
    )

    assert "área legal exacta" in respuesta["messages"][0]["response"]


def test_normalizar_servicio_rechaza_texto_basura(monkeypatch):
    class _TransformadorBasura:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            return ["hola"]

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorBasura,
    )

    resultado = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="hola",
            cliente_openai=object(),
        )
    )

    assert resultado["ok"] is False
    assert "No identifiqué un servicio válido" in resultado["response"]


def test_normalizar_servicio_pide_aclaracion_en_servicio_generico(monkeypatch):
    class _TransformadorGenerico:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            return ["asesoría legal"]

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorGenerico,
    )

    resultado = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="abogado",
            cliente_openai=object(),
        )
    )

    assert resultado["ok"] is False
    assert "área legal exacta" in resultado["response"]


def test_normalizar_servicio_acepta_transporte_y_barco(monkeypatch):
    class _TransformadorTransporte:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            if "barco" in entrada_usuario:
                return ["capitán de barco"]
            return ["conductor de transporte pesado terrestre"]

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorTransporte,
    )

    terrestre = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="conductor de transporte pesado terrestre",
            cliente_openai=object(),
        )
    )
    maritimo = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="capitan de barco",
            cliente_openai=object(),
        )
    )

    assert terrestre["ok"] is True
    assert terrestre["service"] == "conductor de transporte pesado terrestre"
    assert maritimo["ok"] is True
    assert maritimo["service"] == "capitán de barco"


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
        "asesoría para rebaja de pensión alimenticia",
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


def test_agregar_servicios_acepta_servicio_sin_bloqueo_taxonomico(monkeypatch):
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

    assert "transporte de mercancías" in respuesta["messages"][0]["response"]


def test_sanitizador_preserva_texto_natural_para_ui_y_embeddings():
    servicios = modulo_transformador._normalizar_y_limitar_servicios(
        [
            "desarrollo software a medida",
            "automatizacion procesos negocio",
            "desarrollo aplicaciones moviles",
        ],
        5,
        entrada_usuario=(
            "desarrollo de software a medida, automatizacion de procesos de negocio, "
            "desarrollo de aplicaciones moviles"
        ),
    )

    assert servicios == [
        "desarrollo de software a medida",
        "automatización de procesos de negocio",
        "desarrollo de aplicaciones móviles",
    ]


def test_normalizacion_dominios_operativos_consolida_aliases():
    assert (
        modulo_clasificacion.normalizar_domain_code_operativo("alimentación")
        == "gastronomia_alimentos"
    )
    assert (
        modulo_clasificacion.normalizar_domain_code_operativo("educación")
        == "academico"
    )
    assert (
        modulo_clasificacion.normalizar_domain_code_operativo("servicios administrativos")
        == "servicios_administrativos"
    )


def test_service_summary_se_construye_con_categoria_y_dominio():
    summary = modulo_clasificacion.construir_service_summary(
        service_name="Desarrollo de software a medida",
        category_name="desarrollo de software",
        domain_code="tecnologia",
    )

    assert "desarrollo de software" in summary.lower()
    assert "software a medida" in summary.lower()
    assert "servicio especializado" not in summary.lower()


def test_actualizar_servicios_persiste_servicio_sin_canonizacion_taxonomica(monkeypatch):
    import importlib

    modulo_actualizar_servicios = importlib.import_module(
        "services.servicios_proveedor.actualizar_servicios"
    )
    actualizar_servicios = modulo_actualizar_servicios.actualizar_servicios

    class _SupabaseQueryStub:
        def __init__(self, table_name, tables):
            self.table_name = table_name
            self.tables = tables

        def select(self, *_args, **_kwargs):
            return self

        def delete(self, *_args, **_kwargs):
            return self

        def update(self, _payload):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.tables.get(self.table_name, []))

    class _SupabaseStub:
        def __init__(self, tables):
            self.tables = tables

        def table(self, table_name: str):
            return _SupabaseQueryStub(table_name, self.tables)

    supabase = _SupabaseStub(
        {
            "service_taxonomy_publications": [{"version": 1, "status": "published"}],
            "service_domains": [{"id": "dom-1", "code": "legal", "status": "published"}],
            "service_domain_aliases": [
                {
                    "id": "alias-1",
                    "domain_id": "dom-1",
                    "alias_text": "laboralista",
                    "alias_normalized": "laboralista",
                    "canonical_service_id": "canon-1",
                    "status": "published",
                    "is_active": True,
                }
            ],
            "service_canonical_services": [
                {
                    "id": "canon-1",
                    "domain_id": "dom-1",
                    "canonical_name": "abogado laboral",
                    "canonical_normalized": "abogado laboral",
                    "status": "active",
                }
            ],
            "service_precision_rules": [],
            "provider_services": [{"service_name": "laboralista", "display_order": 1}],
            "providers": [{"phone": "593959091325@s.whatsapp.net"}],
        }
    )

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    async def _fake_insertar_servicios_proveedor(
        *, supabase, proveedor_id, servicios, servicio_embeddings
    ):
        assert proveedor_id == "prov-1"
        assert servicios == ["laboralista"]
        return {"inserted_count": 1, "failed_services": []}

    monkeypatch.setattr(modulo_actualizar_servicios, "run_supabase", _fake_run_supabase)
    monkeypatch.setattr(
        "services.registro.insertar_servicios_proveedor",
        _fake_insertar_servicios_proveedor,
    )

    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = supabase
    principal_stub.servicio_embeddings = object()
    sys.modules["principal"] = principal_stub
    flows_sesion_stub = types.ModuleType("flows.sesion")

    async def _fake_invalidar_cache_perfil_proveedor(_telefono):
        return None

    async def _fake_refrescar_cache_perfil_proveedor(_telefono):
        return None

    flows_sesion_stub.invalidar_cache_perfil_proveedor = (
        _fake_invalidar_cache_perfil_proveedor
    )
    flows_sesion_stub.refrescar_cache_perfil_proveedor = (
        _fake_refrescar_cache_perfil_proveedor
    )
    sys.modules["flows.sesion"] = flows_sesion_stub

    resultado = asyncio.run(actualizar_servicios("prov-1", ["laboralista"]))

    assert resultado == ["laboralista"]
