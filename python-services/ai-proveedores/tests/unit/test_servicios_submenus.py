import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

imghdr_stub = types.ModuleType("imghdr")
setattr(imghdr_stub, "what", lambda *args, **kwargs: None)
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.maintenance.services as modulo_services  # noqa: E402
from flows.maintenance import (  # noqa: E402
    views as modulo_views,
)
from infrastructure.openai import transformador_servicios as modulo_transformador  # noqa: E402
from flows.maintenance.services_confirmation import (  # noqa: E402
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
)
from flows.maintenance.wait_certificate import (  # noqa: E402
    manejar_espera_certificado,
)
from flows.maintenance.wait_experience import (  # noqa: E402
    manejar_espera_experiencia,
)
from flows.maintenance.specialty import (  # noqa: E402
    manejar_espera_especialidad,
)
from flows.maintenance.wait_name import (  # noqa: E402
    manejar_espera_nombre,
)
from flows.maintenance.menu import manejar_estado_menu  # noqa: E402
from flows.maintenance.menu import (  # noqa: E402
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
)
from flows.maintenance.services import (  # noqa: E402
    manejar_accion_servicios,
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
)
from flows.maintenance.wait_social import (  # noqa: E402
    manejar_espera_red_social,
)
from flows.onboarding.handlers.redes_sociales import (  # noqa: E402
    manejar_espera_red_social_onboarding,
)
from flows.onboarding.handlers.servicios import (  # noqa: E402
    manejar_espera_servicios_onboarding,
)
from flows.onboarding.handlers.servicios_confirmacion import (  # noqa: E402
    manejar_confirmacion_servicios_onboarding,
    manejar_decision_agregar_otro_servicio_onboarding,
)
from flows.validators.input import (  # noqa: E402
    parsear_entrada_red_social,
)
from flows.router import enrutar_estado  # noqa: E402
from routes.maintenance import manejar_informacion_personal_mantenimiento  # noqa: E402
from principal import normalizar_respuesta_whatsapp  # noqa: E402
from services.shared import interpretar_respuesta  # noqa: E402
from templates.maintenance import (  # noqa: E402
    mensaje_ejemplo_servicio_seleccionado,
    payload_confirmacion_servicios_menu,
    preguntar_nuevo_servicio_con_ejemplos_dinamicos,
)
from services.maintenance.ejemplos_servicios_top import (  # noqa: E402
    obtener_ejemplos_servicios_top,
)
from services.maintenance.redes_sociales_slots import (  # noqa: E402
    extraer_redes_sociales_desde_texto,
)
from templates.maintenance.menus import DETAIL_ACTION_SERVICES_ADD  # noqa: E402
from templates.maintenance.menus import (  # noqa: E402
    DETAIL_ACTION_BACK,
    DETAIL_ACTION_SERVICE_CHANGE,
    DETAIL_ACTION_SERVICE_DELETE,
    DETAIL_ACTION_SOCIAL_CHANGE,
    SERVICE_BACK_ID,
    SERVICE_EXAMPLE_ADMIN_ID,
    SERVICE_EXAMPLE_BACK_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_MECHANICS_ID,
    SERVICE_SLOT_PREFIX,
    SOCIAL_NETWORK_FACEBOOK_ID,
    SOCIAL_NETWORK_INSTAGRAM_ID,
)
from templates.onboarding.registration import (  # noqa: E402
    SOCIAL_FACEBOOK_ID,
    SOCIAL_INSTAGRAM_ID,
    SOCIAL_SKIP_ID,
)
from templates.onboarding import (  # noqa: E402
    REDES_SOCIALES_SKIP_ID,
    payload_redes_sociales_onboarding_con_imagen,
)
from templates.maintenance.menus import payload_ejemplos_servicios_personalizados  # noqa: E402


def test_render_profile_view_normaliza_url_dni_reverso_desde_storage(monkeypatch):
    class _Bucket:
        def create_signed_url(self, path, _ttl):
            return {"signedURL": f"https://signed.example/{path}"}

        def get_public_url(self, path):
            return f"https://public.example/{path}"

    class _Storage:
        def from_(self, _bucket):
            return _Bucket()

    supabase = SimpleNamespace(storage=_Storage())

    monkeypatch.setattr(
        modulo_views,
        "get_supabase_client",
        lambda: supabase,
    )
    monkeypatch.setattr(
        modulo_views,
        "SUPABASE_PROVIDERS_BUCKET",
        "tinkubot-providers",
    )

    flujo = {
        "dni_back_photo_url": (
            "https://euescxureboitxqjduym.supabase.co/storage/v1/object/public/"
            "tinkubot-providers/dni-backs/prov-1.jpg?"
        )
    }

    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo=flujo,
            estado="viewing_personal_dni_back",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["ui"]["type"] == "buttons"
    assert respuesta["ui"]["header_type"] == "image"
    assert (
        respuesta["ui"]["header_media_url"]
        == "https://signed.example/dni-backs/prov-1.jpg"
    )


def test_render_profile_view_limpia_query_string_en_foto_perfil(monkeypatch):
    monkeypatch.setattr(
        modulo_views,
        "get_supabase_client",
        lambda: None,
    )
    monkeypatch.setattr(
        modulo_views,
        "SUPABASE_PROVIDERS_BUCKET",
        "tinkubot-providers",
    )

    flujo = {"face_photo_url": "https://broken.example/photo.jpg?"}

    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo=flujo,
            estado="viewing_personal_photo",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["ui"]["type"] == "buttons"
    assert respuesta["ui"]["header_type"] == "image"
    assert respuesta["ui"]["header_media_url"] == "https://broken.example/photo.jpg"


def test_render_profile_view_certificado_usa_url_resuelta(monkeypatch):
    async def _listar_certificados(_proveedor_id):
        return [
            {
                "id": "cert-1",
                "file_url": "https://invalid.example/cert.jpg?",
                "display_order": 0,
                "status": "active",
            }
        ]

    monkeypatch.setattr(
        modulo_views,
        "listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        modulo_views,
        "_resolver_media_url",
        lambda _url: "https://signed.example/certificates/cert-1.jpg",
    )

    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo={"selected_certificate_id": "cert-1"},
            estado="viewing_professional_certificate",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["response"] == "Certificado seleccionado."
    assert respuesta["ui"]["type"] == "buttons"
    assert respuesta["ui"]["header_type"] == "image"
    assert (
        respuesta["ui"]["header_media_url"]
        == "https://signed.example/certificates/cert-1.jpg"
    )


def test_render_profile_view_certificado_muestra_fallback_si_no_hay_media(monkeypatch):
    async def _listar_certificados(_proveedor_id):
        return [
            {
                "id": "cert-1",
                "file_url": "https://invalid.example/cert.jpg?",
                "display_order": 0,
                "status": "active",
            }
        ]

    monkeypatch.setattr(
        modulo_views,
        "listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(modulo_views, "_resolver_media_url", lambda _url: "")

    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo={"selected_certificate_id": "cert-1"},
            estado="viewing_professional_certificate",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["response"] == "No pudimos cargar el certificado actual."
    assert respuesta["ui"]["type"] == "buttons"
    assert respuesta["ui"]["options"][0]["id"] == "provider_detail_certificates_add"


def test_selector_servicios_abre_agregado_directo():
    async def _fake_prompt(**_kwargs):
        return {
            "response": (
                "Escribe el servicio que quieres agregar.\n"
                "¿Necesitas ideas? Toca Ver ejemplos."
            ),
            "ui": {
                "type": "list",
                "list_button_text": "Ver ejemplos",
                "options": [],
            },
            "service_examples_lookup": {},
        }

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(
        modulo_services,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )
    flujo = {"services": ["plomeria"]}

    try:
        respuesta = asyncio.run(
            manejar_accion_servicios(
                flujo=flujo,
                texto_mensaje="1",
                opcion_menu="1",
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "maintenance_service_add"
    assert respuesta["response"] == (
        "Escribe el servicio que quieres agregar.\n"
        "¿Necesitas ideas? Toca Ver ejemplos."
    )
    assert respuesta["ui"]["type"] == "list"
    assert respuesta["ui"]["list_button_text"] == "Ver ejemplos"


def test_payload_ejemplos_servicios_tiene_tres_opciones():
    payload = payload_ejemplos_servicios_personalizados(
        [
            {
                "id": SERVICE_EXAMPLE_MECHANICS_ID,
                "title": "Gasfitería",
                "description": (
                    "Instalación y mantenimiento de tuberías para casas " "o edificios"
                ),
            },
            {
                "id": SERVICE_EXAMPLE_LEGAL_ID,
                "title": "Legal",
                "description": (
                    "Asesoría legal en divorcios, pensiones y trámites " "de familia"
                ),
            },
            {
                "id": SERVICE_EXAMPLE_ADMIN_ID,
                "title": "Administrativo",
                "description": (
                    "Facturación, cobranza y gestión documental para " "negocios"
                ),
            },
        ],
        indice=4,
        maximo=7,
    )

    assert payload["ui"]["type"] == "list"
    assert payload["ui"]["list_button_text"] == "Ver ejemplos"
    assert payload["ui"]["header_text"] == "Agregar Servicio 4 de 7"
    assert len(payload["ui"]["options"]) == 4
    assert payload["ui"]["options"][0]["id"] == SERVICE_EXAMPLE_MECHANICS_ID
    assert payload["ui"]["options"][1]["id"] == SERVICE_EXAMPLE_LEGAL_ID
    assert payload["ui"]["options"][2]["id"] == SERVICE_EXAMPLE_ADMIN_ID
    assert payload["ui"]["options"][3]["id"] == SERVICE_EXAMPLE_BACK_ID
    assert "Ej.:" not in payload["ui"]["options"][0]["description"]
    assert payload["ui"]["options"][0]["title"] == "Gasfitería"


def test_payload_ejemplos_servicios_trunca_titulos_largos():
    payload = payload_ejemplos_servicios_personalizados(
        [
            {
                "id": "provider_service_example:instalaciones_electricas",
                "title": "Instalaciones eléctricas industriales y residenciales",
                "description": (
                    "Instalación, mantenimiento y certificación de tableros eléctricos"
                ),
            }
        ]
    )

    titulo = payload["ui"]["options"][0]["title"]
    assert len(titulo) <= 24
    assert titulo.endswith("...")


def test_obtener_ejemplos_servicios_top_prioriza_el_dominio_mas_usado(monkeypatch):
    class _Respuesta:
        def __init__(self, data):
            self.data = data

    async def _fake_run_supabase(callable_, label):
        if label == "provider_services.top_examples":
            servicio_gasfiteria_corto = "Cambio de llave"
            servicio_gasfiteria_largo = (
                "Instalación y mantenimiento de tuberías para casas, edificios, "
                "locales comerciales y proyectos industriales"
            )
            servicio_legal = (
                "Asesoría legal en divorcios, pensiones y trámites de familia"
            )
            return _Respuesta(
                [
                    {
                        "domain_code": "gasfiteria",
                        "service_name": servicio_gasfiteria_corto,
                        "service_summary": servicio_gasfiteria_corto,
                        "created_at": "2026-03-19T10:00:00Z",
                    },
                    {
                        "domain_code": "gasfiteria",
                        "service_name": servicio_gasfiteria_largo,
                        "service_summary": servicio_gasfiteria_largo,
                        "created_at": "2026-03-19T11:00:00Z",
                    },
                    {
                        "domain_code": "legal",
                        "service_name": servicio_legal,
                        "service_summary": servicio_legal,
                        "created_at": "2026-03-19T12:00:00Z",
                    },
                ]
            )
        if label == "service_domains.examples_catalog":
            return _Respuesta(
                [
                    {
                        "code": "gasfiteria",
                        "display_name": "Gasfitería",
                        "status": "active",
                    },
                    {
                        "code": "legal",
                        "display_name": "Legal",
                        "status": "active",
                    },
                ]
            )
        return _Respuesta([])

    monkeypatch.setattr(
        "services.maintenance.ejemplos_servicios_top.run_supabase",
        _fake_run_supabase,
    )

    ejemplos = asyncio.run(obtener_ejemplos_servicios_top(supabase=object()))

    assert len(ejemplos) == 2
    assert ejemplos[0]["id"] == "provider_service_example:gasfiteria"
    assert ejemplos[0]["title"] == "Gasfitería"
    assert len(ejemplos[0]["description"]) <= 68
    assert ejemplos[0]["description"].startswith(
        "Instalación y mantenimiento de tuberías"
    )
    assert ejemplos[1]["title"] == "Legal"


def test_selector_servicios_abre_agregado_con_numeracion_contextual():
    async def _fake_prompt(**_kwargs):
        return {
            "response": (
                "Escribe el servicio que quieres agregar.\n"
                "¿Necesitas ideas? Toca Ver ejemplos."
            ),
            "ui": {
                "type": "list",
                "list_button_text": "Ver ejemplos",
                "options": [],
            },
            "service_examples_lookup": {},
        }

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(
        modulo_services,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )
    flujo = {"services": ["servicio 1", "servicio 2", "servicio 3"]}

    try:
        respuesta = asyncio.run(
            manejar_accion_servicios(
                flujo=flujo,
                texto_mensaje="1",
                opcion_menu="1",
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "maintenance_service_add"
    assert respuesta["response"] == (
        "Escribe el servicio que quieres agregar.\n"
        "¿Necesitas ideas? Toca Ver ejemplos."
    )


def test_selector_servicios_muestra_menu_unificado():
    flujo = {"services": ["plomeria"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="9",
            opcion_menu="9",
        )
    )

    assert "Gestión de Servicios" in respuesta["messages"][1]["response"]
    assert "Servicios registrados" in respuesta["messages"][1]["response"]
    assert "plomeria" in respuesta["messages"][1]["response"]


def test_submenu_profesional_servicios_agregar_muestra_secuencia_contextual():
    async def _fake_prompt(**_kwargs):
        return {
            "response": (
                "Escribe el servicio que quieres agregar.\n"
                "¿Necesitas ideas? Toca Ver ejemplos."
            ),
            "ui": {
                "type": "list",
                "list_button_text": "Ver ejemplos",
                "options": [],
            },
            "service_examples_lookup": {},
        }

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(
        modulo_views,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )
    flujo = {
        "services": ["servicio 1", "servicio 2", "servicio 3"],
        "provider_id": "prov-1",
    }

    try:
        respuesta = asyncio.run(
            modulo_views.manejar_vista_perfil(
                flujo=flujo,
                estado="viewing_professional_services",
                texto_mensaje=DETAIL_ACTION_SERVICES_ADD,
                proveedor_id="prov-1",
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "maintenance_service_add"
    assert respuesta["response"] == (
        "Escribe el servicio que quieres agregar.\n"
        "¿Necesitas ideas? Toca Ver ejemplos."
    )
    assert respuesta["ui"]["type"] == "list"
    assert respuesta["ui"]["list_button_text"] == "Ver ejemplos"


def test_selector_servicios_reconoce_ejemplo_de_mecanica():
    flujo = {
        "services": ["plomeria"],
        "service_examples_lookup": {
            "provider_service_example:gasfiteria": {
                "description": (
                    "Instalación y mantenimiento de tuberías para casas o edificios"
                )
            }
        },
    }

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="provider_service_example:gasfiteria",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "maintenance_service_add"
    assert "sugerencia" in respuesta["response"].lower()
    assert "instalación y mantenimiento de tuberías" in respuesta["response"].lower()


def test_selector_servicios_regresa_al_menu_desde_lista():
    flujo = {
        "services": ["plomeria"],
        "state": "maintenance_service_add",
    }

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="",
            selected_option=SERVICE_EXAMPLE_BACK_ID,
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "maintenance_service_action"
    assert "Gestión de Servicios" in respuesta["messages"][0]["response"]


def test_slot_vacio_de_servicio_abre_captura(monkeypatch):
    async def _fake_prompt(**_kwargs):
        return {
            "response": "Prompt servicio",
            "ui": {"type": "list", "options": [], "list_button_text": "Ver ejemplos"},
            "service_examples_lookup": {},
        }

    monkeypatch.setattr(
        modulo_views,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )

    flujo = {"services": ["Plomeria"], "provider_id": "prov-1"}

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_services",
            texto_mensaje=f"{SERVICE_SLOT_PREFIX}4",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_service_add"
    assert flujo["selected_service_index"] == 4
    assert flujo["profile_edit_mode"] == "provider_service_add"
    assert respuesta["response"] == "Prompt servicio"


def test_slot_registrado_de_servicio_abre_detalle():
    flujo = {"services": ["Plomeria", "Electricidad"], "provider_id": "prov-1"}

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_services",
            texto_mensaje=f"{SERVICE_SLOT_PREFIX}1",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "viewing_professional_service"
    assert flujo["selected_service_index"] == 1
    assert respuesta["messages"][0]["ui"]["header_text"] == "Servicio 2"
    assert "Electricidad" in respuesta["messages"][0]["response"]


def test_detalle_servicio_permite_reemplazo(monkeypatch):
    async def _fake_prompt(**_kwargs):
        return {
            "response": "Prompt reemplazo",
            "ui": {"type": "list", "options": [], "list_button_text": "Ver ejemplos"},
            "service_examples_lookup": {},
        }

    monkeypatch.setattr(
        modulo_views,
        "preguntar_nuevo_servicio_con_ejemplos_dinamicos",
        _fake_prompt,
    )

    flujo = {
        "state": "viewing_professional_service",
        "services": ["Plomeria", "Electricidad"],
        "selected_service_index": 1,
        "provider_id": "prov-1",
    }

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_service",
            texto_mensaje=DETAIL_ACTION_SERVICE_CHANGE,
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_service_add"
    assert flujo["profile_edit_mode"] == "provider_service_replace"
    assert respuesta["response"] == "Prompt reemplazo"


def test_detalle_servicio_elimina_y_vuelve_a_slots(monkeypatch):
    async def _eliminar_servicio(_proveedor_id, _indice):
        return ["Plomeria"]

    monkeypatch.setattr(
        "flows.maintenance.views.eliminar_servicio_proveedor",
        _eliminar_servicio,
    )

    flujo = {
        "state": "viewing_professional_service",
        "services": ["Plomeria", "Electricidad"],
        "selected_service_index": 1,
        "provider_id": "prov-1",
    }

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_service",
            texto_mensaje=DETAIL_ACTION_SERVICE_DELETE,
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert flujo["services"] == ["Plomeria"]
    assert respuesta["messages"][0]["ui"]["header_text"] == "Menu - Servicios"


def test_detalle_servicio_regresar_vuelve_a_slots():
    flujo = {
        "state": "viewing_professional_service",
        "services": ["Plomeria", "Electricidad"],
        "selected_service_index": 1,
        "provider_id": "prov-1",
    }

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_service",
            texto_mensaje=DETAIL_ACTION_BACK,
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert respuesta["messages"][0]["ui"]["header_text"] == "Menu - Servicios"


def test_confirmacion_agregar_servicios_persiste_y_regresa_a_menu(monkeypatch):
    async def _agregar_servicios(proveedor_id, servicios):
        return ["desarrollo de software", *servicios]

    monkeypatch.setattr(
        modulo_services,
        "agregar_servicios_proveedor",
        _agregar_servicios,
    )

    flujo = {
        "services": ["desarrollo de software"],
        "service_add_temporales": ["transporte terrestre nacional de carga"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "maintenance_service_action"
    assert flujo["services"] == [
        "desarrollo de software",
        "transporte terrestre nacional de carga",
    ]
    assert (
        "transporte terrestre nacional de carga" in respuesta["messages"][0]["response"]
    )


def test_agregar_servicios_entra_en_confirmacion_antes_de_guardar(monkeypatch):
    async def _fake_normalizar(**_kwargs):
        return {
            "ok": True,
            "services": ["transporte terrestre nacional de carga"],
        }

    monkeypatch.setattr(
        modulo_services,
        "_normalizar_servicios_ingresados",
        _fake_normalizar,
    )

    flujo = {"services": ["desarrollo de software"]}

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="transporte terrestre nacional de carga",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_service_add_confirmation"
    assert flujo["service_add_temporales"] == ["transporte terrestre nacional de carga"]
    assert "¿Los agrego a tu perfil?" in respuesta["messages"][0]["response"]
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Agregar"
    assert respuesta["messages"][0]["ui"]["options"][1]["title"] == "Corregir"


def test_agregar_servicios_valido_sin_aclaracion_por_domino(monkeypatch):
    class _TransformadorOK:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, *args, **kwargs):
            return ["diseño y gestión de proyectos tecnológicos para empresas públicas"]

    async def _validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "catalog_review_required",
            "domain_code": "tecnologia",
            "resolved_domain_code": None,
            "proposed_category_name": "proyectos tecnológicos",
            "proposed_service_summary": f"Servicio de {servicio}.",
            "service_summary": f"Servicio de {servicio}.",
            "reason": "ai_validation",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        modulo_services,
        "TransformadorServicios",
        _TransformadorOK,
    )
    monkeypatch.setattr(
        "flows.maintenance.services.validar_servicio_semanticamente",
        _validar_servicio_semanticamente,
    )

    flujo = {"services": ["desarrollo de software"]}

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje=(
                "diseño y gestión de proyectos tecnológicos para empresas públicas"
            ),
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_service_add_confirmation"
    assert flujo["service_add_temporales"] == [
        "diseño y gestión de proyectos tecnológicos para empresas públicas"
    ]
    assert "¿Los agrego a tu perfil?" in respuesta["messages"][0]["response"]


def test_confirmacion_agregar_servicios_acepta_selected_option_button(monkeypatch):
    async def _agregar_servicios(proveedor_id, servicios):
        return ["Pintura interior", *servicios]

    monkeypatch.setattr(
        "flows.maintenance.services.agregar_servicios_proveedor",
        _agregar_servicios,
    )

    flujo = {
        "state": "maintenance_service_add_confirmation",
        "services": ["Pintura interior"],
        "service_add_temporales": ["plomería"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-123",
            texto_mensaje="",
            selected_option="profile_service_confirm",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_service_action"
    assert flujo["services"] == ["Pintura interior", "plomería"]
    assert "Gestión de Servicios" in respuesta["messages"][0]["response"]
    assert "plomería" in respuesta["messages"][0]["response"]


def test_confirmacion_agregar_servicios_reemplaza_slot_desde_menu(monkeypatch):
    async def _actualizar_servicios(_proveedor_id, servicios):
        return servicios

    monkeypatch.setattr(
        "flows.maintenance.services.actualizar_servicios",
        _actualizar_servicios,
    )

    flujo = {
        "state": "maintenance_service_add_confirmation",
        "services": ["Pintura interior", "Electricidad"],
        "service_add_temporales": ["Plomería"],
        "profile_edit_mode": "provider_service_replace",
        "profile_return_state": "viewing_professional_services",
        "selected_service_index": 1,
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-123",
            texto_mensaje="Agregar",
            selected_option=None,
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert flujo["services"] == ["Pintura interior", "Plomería"]
    assert "profile_edit_mode" not in flujo
    assert "selected_service_index" not in flujo
    assert respuesta["messages"][0]["ui"]["header_text"] == "Menu - Servicios"


def test_confirmacion_agregar_servicios_acepta_texto_agregar(monkeypatch):
    async def _agregar_servicios(proveedor_id, servicios):
        return ["Pintura interior", *servicios]

    monkeypatch.setattr(
        "flows.maintenance.services.agregar_servicios_proveedor",
        _agregar_servicios,
    )

    flujo = {
        "state": "maintenance_service_add_confirmation",
        "services": ["Pintura interior"],
        "service_add_temporales": ["plomería"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-123",
            texto_mensaje="Agregar",
            selected_option=None,
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_service_action"
    assert flujo["services"] == ["Pintura interior", "plomería"]
    assert "Gestión de Servicios" in respuesta["messages"][0]["response"]
    assert "plomería" in respuesta["messages"][0]["response"]


def test_confirmacion_agregar_servicios_reintento_consumido_por_nonce(
    monkeypatch,
):
    class _RedisStub:
        def __init__(self):
            self.keys = {"service_add_confirmation_consumed:prov-123:nonce-x"}

        async def set_if_absent(self, key, value, expire=None):
            if key in self.keys:
                return False
            self.keys.add(key)
            return True

    async def _render_profile_view(*args, **kwargs):
        return {"response": "Vista actualizada"}

    async def _agregar_servicios(proveedor_id, servicios):
        raise AssertionError("No debe volver a persistir un reintento duplicado")

    monkeypatch.setattr(
        "flows.maintenance.services.cliente_redis",
        _RedisStub(),
    )
    monkeypatch.setattr(
        "flows.maintenance.services.agregar_servicios_proveedor",
        _agregar_servicios,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.render_profile_view",
        _render_profile_view,
    )

    flujo = {
        "state": "maintenance_service_add_confirmation",
        "services": ["Pintura interior"],
        "service_add_temporales": ["plomería"],
        "service_add_confirmation_nonce": "nonce-x",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-123",
            texto_mensaje="Agregar",
            selected_option=None,
            cliente_openai=object(),
        )
    )

    assert respuesta["messages"][0]["response"] == "Vista actualizada"
    assert flujo["services"] == ["Pintura interior"]


def test_confirmacion_agregar_servicios_con_siete_registrados_informa_limite():
    flujo = {
        "services": [f"servicio {idx}" for idx in range(1, 11)],
        "service_add_temporales": ["transporte terrestre nacional de carga"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id="prov-1",
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "maintenance_service_action"
    assert (
        "ya tienes 10 servicios registrados"
        in respuesta["messages"][0]["response"].lower()
    )
    assert "Gestión de Servicios" in respuesta["messages"][1]["response"]


def test_menu_completar_perfil_abre_flujo_profesional_desde_cero():
    flujo = {"services": [], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="completar perfil",
            opcion_menu=None,
            esta_registrado=True,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "maintenance_experience"
    assert "años de experiencia" in respuesta["messages"][0]["response"].lower()


def test_menu_completar_perfil_reusa_servicios_existentes():
    flujo = {"services": ["plomeria"], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="completar perfil",
            opcion_menu=None,
            esta_registrado=True,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "maintenance_experience"
    assert flujo["servicios_temporales"] == ["plomeria"]
    assert "años de experiencia" in respuesta["messages"][0]["response"].lower()


def test_menu_approved_basic_mantiene_menu_operativo():
    flujo = {
        "services": [],
        "approved_basic": True,
        "full_name": "Diego Unkuch Gonzalez",
    }

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="2",
            opcion_menu="2",
            esta_registrado=True,
        )
    )

    assert len(respuesta["messages"]) == 1
    assert (
        "información profesional"
        in respuesta["messages"][0]["response"].lower()
    )


def test_menu_aprobado_abre_submenu_informacion_personal():
    flujo = {"services": ["plomeria"], "approved_basic": False}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="provider_menu_info_personal",
            opcion_menu=None,
            esta_registrado=True,
        )
    )

    assert flujo["state"] == "awaiting_personal_info_action"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert (
        respuesta["messages"][0]["ui"]["options"][0]["id"]
        == "provider_submenu_personal_nombre"
    )


def test_submenu_personal_nombre_inicia_actualizacion():
    flujo = {"approved_basic": False, "full_name": "Maria Lopez"}

    respuesta = asyncio.run(
        manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje="provider_submenu_personal_nombre",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "viewing_personal_name"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert (
        respuesta["messages"][0]["ui"]["options"][0]["id"]
        == "provider_detail_name_change"
    )


def test_submenu_personal_foto_no_se_interpreta_como_opcion_dos():
    texto = "provider_submenu_personal_foto"
    flujo = {
        "state": "awaiting_personal_info_action",
        "approved_basic": False,
        "face_photo_url": "https://example.com/photo.jpg",
    }

    respuesta = asyncio.run(
        manejar_informacion_personal_mantenimiento(
            flujo=flujo,
            texto_mensaje=texto,
            opcion_menu=interpretar_respuesta(texto, "menu"),
        )
    )

    assert flujo["state"] == "viewing_personal_photo"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["header_type"] == "image"
    assert (
        respuesta["messages"][0]["ui"]["header_media_url"]
        == "https://example.com/photo.jpg"
    )
    assert (
        respuesta["messages"][0]["ui"]["options"][0]["id"]
        == "provider_detail_photo_change"
    )


def test_vista_dni_reverso_cambia_solo_reverso():
    flujo = {"approved_basic": False}

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_personal_dni_back",
            texto_mensaje="provider_detail_dni_back_change",
            proveedor_id="prov-1",
        )
    )

    assert flujo["profile_edit_mode"] == "personal_dni_back_update"
    assert flujo["state"] == "maintenance_dni_back_photo_update"
    assert "parte posterior" in respuesta["messages"][0]["response"].lower()


def test_headers_menus_interactivos_son_consistentes():
    from templates.maintenance.menus import (
        SERVICE_BACK_ID,
        SERVICE_DELETE_BACK_ID,
        payload_detalle_servicios,
        payload_lista_eliminar_servicios,
        payload_menu_post_registro_proveedor,
        payload_submenu_informacion_personal,
        payload_submenu_informacion_profesional,
    )

    principal = payload_menu_post_registro_proveedor()
    personal = payload_submenu_informacion_personal()
    profesional = payload_submenu_informacion_profesional()
    servicios = payload_detalle_servicios(
        [
            "Plomeria",
            (
                "Servicio extremadamente largo que supera el maximo permitido "
                "por Meta para la descripcion de una fila"
            ),
        ],
        7,
    )

    assert principal["ui"]["header_text"] == "Menu - Principal"
    assert personal["ui"]["header_text"] == "Menu - Informacion Personal"
    assert profesional["ui"]["header_text"] == "Menu - Informacion Profesional"
    assert servicios["ui"]["header_text"] == "Menu - Servicios"
    assert servicios["ui"]["options"][0]["title"] == "Servicio 1"
    assert servicios["ui"]["options"][0]["description"] == "Plomeria"
    assert len(servicios["ui"]["options"][1]["description"]) <= 72
    assert servicios["ui"]["options"][2]["description"] == "No registrado"
    assert servicios["ui"]["options"][-1]["id"] == SERVICE_BACK_ID

    eliminacion = payload_lista_eliminar_servicios(
        [
            (
                "Servicio extremadamente largo que supera el maximo permitido "
                "por Meta para la descripcion de una fila"
            ),
        ]
    )
    assert eliminacion["ui"]["header_text"] == "Menu - Eliminar Servicios"
    assert len(eliminacion["ui"]["options"][0]["description"]) <= 72
    assert eliminacion["ui"]["options"][-1]["id"] == SERVICE_DELETE_BACK_ID


def test_eliminar_servicio_acepta_selected_option_interactivo(monkeypatch):
    async def _eliminar_servicio_proveedor(_proveedor_id, _indice):
        return ["Plomeria"]

    monkeypatch.setattr(
        "flows.maintenance.services.eliminar_servicio_proveedor",
        _eliminar_servicio_proveedor,
    )

    flujo = {
        "state": "maintenance_service_remove",
        "provider_id": "prov-1",
        "services": ["Plomeria", "Electricidad"],
    }

    respuesta = asyncio.run(
        enrutar_estado(
            estado="maintenance_service_remove",
            flujo=flujo,
            texto_mensaje="",
            carga={"selected_option": "provider_service_delete:1"},
            telefono="593999111200@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=SimpleNamespace(info=lambda *a, **k: None),
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert flujo["services"] == ["Plomeria"]
    assert (
        respuesta["response"]["messages"][0]["ui"]["header_text"] == "Menu - Servicios"
    )
    assert (
        respuesta["response"]["messages"][0]["ui"]["options"][0]["description"]
        == "Plomeria"
    )


def test_eliminar_servicio_regresar_vuelve_a_detalle():
    flujo = {
        "state": "maintenance_service_remove",
        "provider_id": "prov-1",
        "services": ["Plomeria", "Electricidad"],
    }

    respuesta = asyncio.run(
        enrutar_estado(
            estado="maintenance_service_remove",
            flujo=flujo,
            texto_mensaje="",
            carga={"selected_option": "provider_service_delete_back"},
            telefono="593999111200@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=SimpleNamespace(info=lambda *a, **k: None),
        )
    )

    assert flujo["state"] == "viewing_professional_services"
    assert (
        respuesta["response"]["messages"][0]["ui"]["header_text"] == "Menu - Servicios"
    )


def test_submenu_profesional_certificado_inicia_reemplazo():
    async def _listar_certificados(_proveedor_id):
        return [{"id": "cert-1", "file_url": "https://example.com/cert.jpg"}]

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(
        "flows.maintenance.menu.listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )

    flujo = {"approved_basic": False, "provider_id": "prov-1"}

    try:
        respuesta = asyncio.run(
            manejar_submenu_informacion_profesional(
                flujo=flujo,
                texto_mensaje="provider_submenu_profesional_certificados",
                opcion_menu=None,
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "viewing_professional_certificates"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Certificado 1"
    assert respuesta["messages"][0]["ui"]["options"][0]["description"] == "Registrado"


def test_submenu_profesional_certificados_varios_muestra_lista():
    async def _listar_certificados(_proveedor_id):
        return [
            {"id": "cert-1", "file_url": "https://example.com/cert-1.jpg"},
            {"id": "cert-2", "file_url": "https://example.com/cert-2.jpg"},
        ]

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(
        "flows.maintenance.menu.listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )

    flujo = {"approved_basic": False, "provider_id": "prov-1"}

    try:
        respuesta = asyncio.run(
            manejar_submenu_informacion_profesional(
                flujo=flujo,
                texto_mensaje="provider_submenu_profesional_certificados",
                opcion_menu=None,
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "viewing_professional_certificates"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["description"] == "Registrado"
    assert respuesta["messages"][0]["ui"]["options"][1]["description"] == "Registrado"
    assert respuesta["messages"][0]["ui"]["options"][2]["description"] == "No registrado"


def test_normalizar_respuesta_whatsapp_aplana_respuestas_anidadas():
    respuesta = normalizar_respuesta_whatsapp(
        {
            "success": True,
            "messages": [
                {
                    "response": [
                        {
                            "response": "",
                            "media_url": "https://example.com/cert-1.jpg",
                            "media_type": "image",
                        },
                        {
                            "response": "Certificado seleccionado.",
                            "ui": {"type": "buttons", "options": []},
                        },
                    ]
                }
            ],
        }
    )

    assert respuesta["success"] is True
    assert len(respuesta["messages"]) == 2
    assert respuesta["messages"][0]["response"] == ""
    assert respuesta["messages"][0]["media_url"] == "https://example.com/cert-1.jpg"
    assert respuesta["messages"][1]["response"] == "Certificado seleccionado."
    assert respuesta["messages"][1]["ui"]["type"] == "buttons"


def test_menu_funciona_como_rescate_en_vista_certificado():
    flujo = {
        "state": "viewing_professional_certificate",
        "approved_basic": False,
        "provider_id": "prov-1",
        "selected_certificate_id": "cert-1",
        "profile_return_state": "viewing_professional_certificates",
    }

    respuesta = asyncio.run(
        enrutar_estado(
            estado="viewing_professional_certificate",
            flujo=flujo,
            texto_mensaje="Menu",
            carga={},
            telefono="593959091325@s.whatsapp.net",
            opcion_menu="5",
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor={"id": "prov-1"},
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert "selected_certificate_id" not in flujo
    assert "profile_return_state" not in flujo
    assert respuesta["persist_flow"] is True
    assert respuesta["response"]["messages"][0]["ui"]["type"] == "list"


def test_submenu_profesional_certificados_sin_items_muestra_slots(monkeypatch):
    async def _listar_certificados(_proveedor_id):
        return []

    monkeypatch.setattr(
        "flows.maintenance.menu.listar_certificados_proveedor",
        _listar_certificados,
    )
    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )

    flujo = {"approved_basic": False, "provider_id": "prov-1"}

    respuesta = asyncio.run(
        manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="provider_submenu_profesional_certificados",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "viewing_professional_certificates"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["description"] == "No registrado"
    assert respuesta["messages"][0]["ui"]["options"][1]["description"] == "No registrado"
    assert respuesta["messages"][0]["ui"]["options"][2]["description"] == "No registrado"


def test_slot_vacio_de_certificado_abre_carga(monkeypatch):
    async def _listar_certificados(_proveedor_id):
        return []

    monkeypatch.setattr(
        "flows.maintenance.views.listar_certificados_proveedor",
        _listar_certificados,
    )

    flujo = {
        "state": "viewing_professional_certificates",
        "approved_basic": False,
        "provider_id": "prov-1",
    }

    respuesta = asyncio.run(
        modulo_views.manejar_vista_perfil(
            flujo=flujo,
            estado="viewing_professional_certificates",
            texto_mensaje="provider_certificate_slot:0",
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_certificate"
    assert flujo["profile_edit_mode"] == "provider_certificate_add"
    assert flujo["profile_return_state"] == "viewing_professional_certificates"
    assert "certificado profesional" in respuesta["messages"][0]["response"].lower()


def test_submenu_profesional_redes_abre_sublista():
    flujo = {
        "approved_basic": False,
        "provider_id": "prov-1",
        "instagram_username": "test",
    }

    respuesta = asyncio.run(
        manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="provider_submenu_profesional_redes",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "viewing_professional_social"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == SOCIAL_NETWORK_FACEBOOK_ID
    assert respuesta["messages"][0]["ui"]["options"][1]["id"] == SOCIAL_NETWORK_INSTAGRAM_ID
    assert respuesta["messages"][0]["ui"]["options"][1]["description"] == "Registrada"


def test_submenu_profesional_experiencia_abre_detalle():
    flujo = {
        "approved_basic": False,
        "provider_id": "prov-1",
        "experience_years": 10,
    }

    respuesta = asyncio.run(
        manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="provider_submenu_profesional_experiencia",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "viewing_professional_experience"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == (
        "provider_detail_experience_change"
    )
    assert "10 años" in respuesta["messages"][0]["response"].lower()


def test_actualizacion_experiencia_desde_menu_regresa_detalle():
    flujo = {
        "state": "onboarding_experience",
        "profile_edit_mode": "experience",
        "profile_return_state": "viewing_professional_experience",
        "experience_years": 3,
    }

    respuesta = asyncio.run(manejar_espera_experiencia(flujo, "8"))

    assert flujo["state"] == "viewing_professional_experience"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["header_text"] == "Experiencia general"
    assert "5 a 10 años" in respuesta["messages"][0]["response"].lower()


def test_redes_sociales_sin_datos_muestra_sublista_vacia():
    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo={"facebook_username": None, "instagram_username": None},
            estado="viewing_professional_social",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["ui"]["type"] == "list"
    assert respuesta["ui"]["options"][0]["description"] == "No registrada"
    assert respuesta["ui"]["options"][1]["description"] == "No registrada"


def test_render_profile_view_detalle_facebook():
    respuesta = asyncio.run(
        modulo_views.render_profile_view(
            flujo={"facebook_username": "diego.unkuch"},
            estado="viewing_professional_social_facebook",
            proveedor_id="prov-1",
        )
    )

    assert respuesta["ui"]["type"] == "buttons"
    assert respuesta["ui"]["options"][0]["id"] == DETAIL_ACTION_SOCIAL_CHANGE
    assert "diego.unkuch" in respuesta["response"].lower()
    assert "facebook.com/diego.unkuch" in respuesta["response"].lower()


def test_actualizacion_red_facebook_desde_router(monkeypatch):
    async def _actualizar_redes_sociales(
        _supabase,
        _proveedor_id,
        *,
        facebook_username,
        instagram_username,
        preferred_type,
    ):
        assert facebook_username == "diego.unkuch"
        assert instagram_username is None
        assert preferred_type == "facebook"
        return {
            "success": True,
            "social_media_url": "https://facebook.com/diego.unkuch",
            "social_media_type": "facebook",
            "facebook_username": "diego.unkuch",
            "instagram_username": None,
        }

    monkeypatch.setattr(
        "flows.maintenance.social_update.actualizar_redes_sociales",
        _actualizar_redes_sociales,
    )

    respuesta = asyncio.run(
        enrutar_estado(
            estado="maintenance_social_facebook_username",
            flujo={
                "state": "maintenance_social_facebook_username",
                "provider_id": "prov-1",
                "profile_return_state": "viewing_professional_social_facebook",
                "current_social_network": "facebook",
                "approved_basic": False,
            },
            texto_mensaje="diego.unkuch",
            carga={},
            telefono="593959091325@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor={"id": "prov-1"},
            supabase=object(),
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )

    assert respuesta["persist_flow"] is True
    assert respuesta["response"]["messages"][0]["response"] == "Redes sociales actualizadas."
    assert respuesta["response"]["messages"][1]["ui"]["type"] == "buttons"


def test_parsear_entrada_red_social_acepta_username_con_arroba():
    resultado = parsear_entrada_red_social("@diego_unkuch")

    assert resultado["type"] == "instagram"
    assert resultado["url"] == "https://instagram.com/diego_unkuch"


def test_extraer_redes_sociales_desde_texto_en_una_sola_linea():
    resultado = extraer_redes_sociales_desde_texto(
        "1 facebook:diego.unkuch 2 instagram:@diegou"
    )

    assert resultado["facebook_username"] == "diego.unkuch"
    assert resultado["instagram_username"] == "diegou"


def test_extraer_redes_sociales_desde_texto_rechaza_texto_ambiguo():
    resultado = extraer_redes_sociales_desde_texto("Qué dices no entiendo")

    assert resultado["facebook_username"] is None
    assert resultado["instagram_username"] is None


def test_payload_redes_sociales_onboarding_usa_env_override(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-image.png",
    )

    respuesta = payload_redes_sociales_onboarding_con_imagen()

    assert respuesta["ui"]["header_type"] == "image"
    assert (
        respuesta["ui"]["header_media_url"]
        == "https://example.com/social-image.png"
    )
    assert respuesta["ui"]["options"][0]["id"] == REDES_SOCIALES_SKIP_ID


@pytest.mark.asyncio
async def test_onboarding_servicios_confirmados_abren_redes_onboarding(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-image.png",
    )
    flujo = {
        "state": "onboarding_services_confirmation",
        "servicios_temporales": ["desarrollo de software", "soporte técnico"],
    }

    respuesta = await manejar_confirmacion_servicios_onboarding(
        flujo=flujo,
        texto_mensaje=None,
        selected_option="profile_service_confirm",
        cliente_openai=None,
    )

    assert flujo["state"] == "onboarding_social_media"
    assert respuesta["messages"][0]["ui"]["header_type"] == "image"
    assert (
        respuesta["messages"][0]["ui"]["header_media_url"]
        == "https://example.com/social-image.png"
    )


@pytest.mark.asyncio
async def test_onboarding_agregar_otro_servicio_no_repite_imagen(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SERVICES_IMAGE_URL",
        "https://example.com/services-image.png",
    )
    flujo = {
        "state": "onboarding_add_another_service",
        "services_guide_shown": True,
        "servicios_temporales": ["desarrollo de software", "soporte técnico"],
    }

    respuesta = await manejar_decision_agregar_otro_servicio_onboarding(
        flujo=flujo,
        texto_mensaje="si",
        selected_option=None,
    )

    assert flujo["state"] == "onboarding_specialty"
    assert respuesta["messages"][0]["response"].startswith(
        "*Describe el servicio que ofreces*"
    )
    assert "media_type" not in respuesta["messages"][0]
    assert "media_url" not in respuesta["messages"][0]


@pytest.mark.asyncio
async def test_onboarding_servicios_uno_a_uno_guarda_detalle_y_pregunta_otro(
    monkeypatch,
):
    class _TransformadorLinea:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            return ["instalaciones eléctricas domiciliarias"]

    async def _fake_validar_servicio_semanticamente(**kwargs):
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": kwargs["service_name"],
            "domain_resolution_status": "matched",
            "domain_code": "construccion_hogar",
            "resolved_domain_code": "construccion_hogar",
            "proposed_category_name": "Electricidad domiciliaria",
            "proposed_service_summary": (
                "Realizo trabajos de instalaciones eléctricas domiciliarias."
            ),
            "confidence": 0.91,
            "classification_confidence": 0.91,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorLinea,
    )
    monkeypatch.setattr(
        "flows.onboarding.handlers.servicios.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )

    flujo = {"state": "onboarding_specialty"}

    respuesta = await manejar_espera_servicios_onboarding(
        flujo=flujo,
        texto_mensaje="instalaciones electricas",
        cliente_openai=object(),
    )

    assert flujo["state"] == "onboarding_add_another_service"
    assert flujo["servicios_temporales"] == [
        "instalaciones eléctricas domiciliarias"
    ]
    assert flujo["servicios_detallados"][0]["raw_service_text"] == (
        "instalaciones electricas"
    )
    assert flujo["servicios_detallados"][0]["service_name"] == (
        "instalaciones eléctricas domiciliarias"
    )
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Sí"
    assert respuesta["messages"][0]["ui"]["options"][1]["title"] == "No"


@pytest.mark.asyncio
async def test_onboarding_redes_sociales_omite_y_va_a_consentimiento(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-image.png",
    )
    flujo = {"state": "onboarding_social_media", "provider_id": "prov-1"}

    respuesta = await manejar_espera_red_social_onboarding(
        flujo=flujo,
        texto_mensaje=None,
        selected_option=REDES_SOCIALES_SKIP_ID,
    )

    assert flujo["state"] == "pending_verification"
    assert "registramos tu información" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_onboarding_redes_sociales_parsea_ambas_en_una_linea(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-image.png",
    )
    updates = {}

    class _FakeQuery:
        def update(self, payload):
            updates.update(payload)
            return self

        def eq(self, *_args, **_kwargs):
            return self

        async def execute(self):
            return SimpleNamespace(data=[{"id": "prov-1"}])

    class _FakeSupabase:
        def table(self, _table_name):
            return _FakeQuery()

    async def _fake_run_supabase(func, **_kwargs):
        return await func()

    monkeypatch.setattr(
        "flows.onboarding.handlers.redes_sociales.run_supabase",
        _fake_run_supabase,
    )
    flujo = {
        "state": "onboarding_social_media",
        "provider_id": "prov-1",
    }

    respuesta = await manejar_espera_red_social_onboarding(
        flujo=flujo,
        texto_mensaje="1 facebook:diego.unkuch 2 instagram:@diegou",
        supabase=_FakeSupabase(),
    )

    assert flujo["state"] == "pending_verification"
    assert flujo["facebook_username"] == "diego.unkuch"
    assert flujo["instagram_username"] == "diegou"
    assert flujo["social_media_type"] == "instagram"
    assert updates["facebook_username"] == "diego.unkuch"
    assert updates["instagram_username"] == "diegou"
    assert "registramos tu información" in respuesta["messages"][0]["response"].lower()


@pytest.mark.asyncio
async def test_onboarding_redes_sociales_persiste_en_supabase(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-image.png",
    )

    updates = {}

    class _FakeQuery:
        def __init__(self, table_name: str):
            self.table_name = table_name

        def update(self, payload):
            updates.update(payload)
            return self

        def eq(self, *_args, **_kwargs):
            return self

        async def execute(self):
            return SimpleNamespace(data=[{"id": "prov-1"}])

    class _FakeSupabase:
        def table(self, table_name: str):
            assert table_name == "providers"
            return _FakeQuery(table_name)

    async def _fake_run_supabase(func, **_kwargs):
        return await func()

    monkeypatch.setattr(
        "flows.onboarding.handlers.redes_sociales.run_supabase",
        _fake_run_supabase,
    )

    flujo = {
        "state": "onboarding_social_media",
        "provider_id": "prov-1",
    }

    respuesta = await manejar_espera_red_social_onboarding(
        flujo=flujo,
        texto_mensaje="Facebook: diego.unkuch",
        supabase=_FakeSupabase(),
    )

    assert flujo["state"] == "pending_verification"
    assert updates["facebook_username"] == "diego.unkuch"
    assert updates["social_media_url"] == "https://facebook.com/diego.unkuch"
    assert updates["social_media_type"] == "facebook"
    assert "updated_at" in updates
    assert "registramos tu información" in respuesta["messages"][0]["response"].lower()


def test_onboarding_redes_sociales_abre_sublista():
    flujo = {"profile_completion_mode": True}

    respuesta = asyncio.run(manejar_espera_experiencia(flujo, "3"))

    assert flujo["state"] == "awaiting_social_media"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == SOCIAL_FACEBOOK_ID
    assert respuesta["messages"][0]["ui"]["options"][1]["id"] == SOCIAL_INSTAGRAM_ID
    assert respuesta["messages"][0]["ui"]["options"][2]["id"] == SOCIAL_SKIP_ID


def test_onboarding_redes_sociales_pide_usuario_de_facebook():
    flujo = {"profile_completion_mode": True, "state": "awaiting_social_media"}

    respuesta = manejar_espera_red_social(
        flujo,
        None,
        selected_option=SOCIAL_FACEBOOK_ID,
    )

    assert flujo["state"] == "onboarding_social_facebook_username"
    assert "facebook" in respuesta["messages"][0]["response"].lower()


def test_onboarding_redes_sociales_registra_usuario_y_vuelve_a_lista():
    flujo = {
        "profile_completion_mode": True,
        "state": "onboarding_social_facebook_username",
    }

    respuesta = manejar_espera_red_social(flujo, "@diego.unkuch")

    assert flujo["state"] == "awaiting_social_media"
    assert flujo["facebook_username"] == "diego.unkuch"
    assert flujo["social_media_type"] == "facebook"
    assert respuesta["messages"][0]["ui"]["type"] == "list"


def test_onboarding_redes_sociales_continuar_avanza_a_certificado():
    flujo = {"profile_completion_mode": True, "state": "awaiting_social_media"}

    respuesta = manejar_espera_red_social(
        flujo,
        None,
        selected_option=SOCIAL_SKIP_ID,
    )

    assert flujo["state"] == "awaiting_certificate"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"


def test_onboarding_redes_sociales_continuar_conserva_red_ya_registrada():
    flujo = {
        "profile_completion_mode": True,
        "state": "awaiting_social_media",
        "facebook_username": "diego.unkuch",
        "social_media_type": "facebook",
    }

    respuesta = manejar_espera_red_social(
        flujo,
        None,
        selected_option=SOCIAL_SKIP_ID,
    )

    assert flujo["state"] == "awaiting_certificate"
    assert flujo["facebook_username"] == "diego.unkuch"
    assert flujo["social_media_type"] == "facebook"
    assert flujo["social_media_url"] == "https://facebook.com/diego.unkuch"
    assert respuesta["messages"][0]["ui"]["header_text"] == "Agregar Certificado"


def test_onboarding_servicio_prompt_muestra_lista_de_ejemplos(monkeypatch):
    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo={"profile_completion_mode": True, "servicios_temporales": []},
            texto_mensaje=SOCIAL_SKIP_ID,
            selected_option=None,
        )
    )

    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][0]["media_url"]
    assert respuesta["messages"][0]["response"] == (
        "*Describe el servicio que ofreces*\n\n"
        "Escribe solo un servicio por mensaje. "
        "Mientras más claro y detallado sea, mejor podremos clasificarlo."
    )


def test_onboarding_servicio_ejemplo_devuelve_sugerencia_y_mantiene_lista(monkeypatch):
    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo={
                "profile_completion_mode": True,
                "state": "onboarding_specialty",
                "servicios_temporales": [],
                "service_examples_lookup": {
                    "provider_service_example_mechanics": {
                        "id": "provider_service_example_mechanics",
                        "title": "Gasfitería",
                    }
                },
            },
            texto_mensaje=None,
            selected_option="provider_service_example_mechanics",
        )
    )

    assert "gasfiter" in respuesta["messages"][0]["response"].lower()
    assert respuesta["messages"][1]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][1]["media_url"]


def test_espera_nombre_mantenimiento_salta_a_cedula_frontal():
    flujo = {
        "state": "maintenance_name",
        "profile_edit_mode": "personal_name",
        "approved_basic": False,
        "full_name": "Maria Lopez",
        "city": "cuenca",
    }

    respuesta = asyncio.run(
        manejar_espera_nombre(
            flujo,
            "maria lopez",
            supabase=object(),
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "maintenance_dni_front_photo_update"
    assert respuesta["messages"][0]["media_type"] == "image"
    assert (
        "cédula" in respuesta["messages"][0]["response"].lower()
    )
def test_completar_perfil_envia_a_revision_humana(monkeypatch):
    async def _actualizar_perfil_profesional(**kwargs):
        return {"success": True}

    async def _agregar_certificado_proveedor(**kwargs):
        return {"success": True}

    monkeypatch.setattr(
        "flows.router.actualizar_perfil_profesional", _actualizar_perfil_profesional
    )
    monkeypatch.setattr(
        "flows.router.agregar_certificado_proveedor", _agregar_certificado_proveedor
    )

    flujo = {
        "state": "maintenance_profile_completion_confirmation",
        "approved_basic": True,
        "profile_completion_mode": True,
        "provider_id": "prov-basic",
        "experience_years": 5,
        "social_media_url": None,
        "social_media_type": None,
        "certificate_uploaded": True,
        "pending_certificate_file_url": "https://example.com/cert.jpg",
        "servicios_temporales": [
            "plomeria residencial",
            "mantenimiento de tuberias",
            "deteccion de fugas",
        ],
    }

    respuesta = asyncio.run(
        enrutar_estado(
            estado=flujo["state"],
            flujo=flujo,
            texto_mensaje="",
            carga={"selected_option": "confirm_accept"},
            telefono="593999111200@s.whatsapp.net",
            opcion_menu=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=SimpleNamespace(info=lambda *a, **k: None),
        )
    )

    assert flujo["approved_basic"] is True
    assert flujo["profile_pending_review"] is False
    assert flujo["state"] == "awaiting_menu_option"
    assert len(respuesta["response"]["messages"]) == 2
    assert "tu perfil quedó actualizado" in (
        respuesta["response"]["messages"][0]["response"].lower()
    )
    assert (
        respuesta["response"]["messages"][1]["ui"]["id"] == "provider_main_menu_v1"
    )


def test_confirmacion_servicios_exige_minimo_tres_en_perfil():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial", "deteccion de fugas"],
        "state": "onboarding_services_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "onboarding_services_confirmation"
    assert "al menos *3 servicios*" in respuesta["messages"][0]["response"].lower()


def test_decision_no_continuar_exige_minimo_tres_en_perfil():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial", "deteccion de fugas"],
        "state": "onboarding_add_another_service",
    }

    respuesta = asyncio.run(
        manejar_decision_agregar_otro_servicio(
            flujo=flujo,
            texto_mensaje="profile_add_another_service_no",
        )
    )

    assert flujo["state"] == "maintenance_specialty"
    assert "al menos *3 servicios*" in respuesta["messages"][0]["response"].lower()
    assert "3/3" in respuesta["messages"][1]["response"].lower()


def test_certificado_omitido_avanza_a_servicios():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial"],
        "provider_id": "prov-1",
        "state": "maintenance_certificate",
    }

    respuesta = asyncio.run(
        manejar_espera_certificado(
            flujo=flujo,
            carga={"selected_option": "skip_profile_certificate"},
        )
    )

    assert flujo["state"] == "maintenance_specialty"
    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][0]["media_url"]
    assert respuesta["messages"][0]["response"].startswith(
        "*Describe el servicio que ofreces*"
    )
    assert "Escribe solo un servicio por mensaje" in respuesta["messages"][0]["response"]


def test_control_viejo_no_se_interpreta_como_servicio():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial"],
        "state": "onboarding_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="skip_profile_certificate",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_specialty"
    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][0]["media_url"]


def test_servicio_perfil_pide_confirmacion_individual(monkeypatch):
    class _TransformadorOK:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, *args, **kwargs):
            return ["desarrollo aplicaciones moviles inteligencia artificial"]

    monkeypatch.setattr(
        "infrastructure.openai.transformador_servicios.TransformadorServicios",
        _TransformadorOK,
    )

    async def _validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": "tecnologia",
            "resolved_domain_code": "tecnologia",
            "proposed_category_name": servicio,
            "proposed_service_summary": f"Servicio de {servicio}.",
            "service_summary": f"Servicio de {servicio}.",
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.maintenance."
        "specialty.validar_servicio_semanticamente",
        _validar_servicio_semanticamente,
    )

    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": [],
        "state": "onboarding_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="desarrollo de software con ia",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_profile_service_confirmation"
    assert flujo["pending_service_candidate"] == (
        "desarrollo aplicaciones moviles " "inteligencia artificial"
    )
    assert (
        respuesta["messages"][0]["ui"]["header_text"]
        == "Servicio 1 de 3 identificado:"
    )
    assert (
        respuesta["messages"][0]["response"]
        == "*desarrollo aplicaciones moviles inteligencia artificial*."
    )
    assert (
        respuesta["messages"][0]["ui"]["footer_text"]
        == "¿Confirmas que es el servicio correcto?"
    )


def test_espera_especialidad_no_interrumpe_si_el_servicio_es_valido_y_domino_no_matchea(
    monkeypatch,
):
    class _TransformadorOK:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, *args, **kwargs):
            return ["diseño y gestión de proyectos tecnológicos para empresas públicas"]

    monkeypatch.setattr(
        "infrastructure.openai.transformador_servicios.TransformadorServicios",
        _TransformadorOK,
    )

    async def _validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "catalog_review_required",
            "domain_code": "tecnologia",
            "resolved_domain_code": None,
            "proposed_category_name": "proyectos tecnológicos",
            "proposed_service_summary": f"Servicio de {servicio}.",
            "service_summary": f"Servicio de {servicio}.",
            "reason": "ai_validation",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.maintenance."
        "specialty.validar_servicio_semanticamente",
        _validar_servicio_semanticamente,
    )

    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": [],
        "state": "onboarding_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje=(
                "diseño y gestión de proyectos tecnológicos para empresas públicas"
            ),
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_profile_service_confirmation"
    assert flujo["pending_service_candidate"] == (
        "diseño y gestión de proyectos tecnológicos para empresas públicas"
    )
    assert (
        respuesta["messages"][0]["ui"]["header_text"]
        == "Servicio 1 de 3 identificado:"
    )
    assert (
        respuesta["messages"][0]["response"]
        == "*diseño y gestión de proyectos tecnológicos para empresas públicas*."
    )
    assert (
        respuesta["messages"][0]["ui"]["footer_text"]
        == "¿Confirmas que es el servicio correcto?"
    )


def test_confirmar_servicio_perfil_avanza_al_siguiente_paso(monkeypatch):
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": [],
        "pending_service_candidate": (
            "desarrollo aplicaciones moviles inteligencia artificial"
        ),
        "pending_service_index": 0,
        "state": "maintenance_profile_service_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje="",
            selected_option="profile_service_confirm",
        )
    )

    assert flujo["state"] == "maintenance_specialty"
    assert flujo["servicios_temporales"] == [
        "desarrollo aplicaciones moviles inteligencia artificial"
    ]
    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][0]["media_url"]
    assert respuesta["messages"][0]["response"].startswith(
        "*Describe el servicio que ofreces*"
    )


def test_tercer_servicio_confirmado_muestra_resumen_final_de_perfil():
    flujo = {
        "profile_completion_mode": True,
        "experience_years": 5,
        "social_media_url": "https://instagram.com/test",
        "certificate_uploaded": True,
        "servicios_temporales": [
            "servicio 1",
            "servicio 2",
        ],
        "pending_service_candidate": "servicio 3",
        "pending_service_index": 2,
        "state": "maintenance_profile_service_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje="",
            selected_option="profile_service_confirm",
        )
    )

    assert flujo["state"] == "pending_verification"
    assert "en revisión" in respuesta["messages"][0]["response"].lower()
    assert "servicio 1" not in respuesta["messages"][0]["response"].lower()


def test_no_acepto_abre_menu_edicion_integral():
    flujo = {
        "profile_completion_mode": True,
        "experience_years": 5,
        "social_media_url": None,
        "certificate_uploaded": False,
        "servicios_temporales": ["servicio 1", "servicio 2", "servicio 3"],
        "state": "maintenance_profile_completion_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_perfil_profesional(
            flujo=flujo,
            texto_mensaje="",
            selected_option="confirm_reject",
        )
    )

    assert flujo["state"] == "maintenance_profile_completion_edit_action"
    assert "qué deseas corregir" in respuesta["messages"][0]["response"].lower()
