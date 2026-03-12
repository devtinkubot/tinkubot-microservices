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
from flows.gestores_estados.gestor_menu import manejar_estado_menu  # noqa: E402
from flows.gestores_estados.gestor_menu import (  # noqa: E402
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
)
from flows.gestores_estados.gestor_espera_nombre import (  # noqa: E402
    manejar_espera_nombre,
)
from flows.gestores_estados.gestor_espera_certificado import (  # noqa: E402
    manejar_espera_certificado,
)
from flows.interpretacion.interpreta_respuesta import interpretar_respuesta  # noqa: E402
from flows.router import enrutar_estado  # noqa: E402
from flows.gestores_estados.gestor_servicios import (  # noqa: E402
    manejar_accion_servicios,
    manejar_confirmacion_agregar_servicios,
)
from flows.gestores_estados.gestor_confirmacion_servicios import (  # noqa: E402
    manejar_decision_agregar_otro_servicio,
)
from flows.gestores_estados.gestor_confirmacion_servicios import (  # noqa: E402
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
)
from flows.gestores_estados.gestor_espera_certificado import (  # noqa: E402
    manejar_espera_certificado,
)
from flows.gestores_estados.gestor_espera_especialidad import (  # noqa: E402
    manejar_espera_especialidad,
)


def test_selector_servicios_abre_agregado_directo():
    flujo = {"services": ["plomeria"]}

    respuesta = asyncio.run(
        manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            opcion_menu="1",
        )
    )

    assert flujo["state"] == "awaiting_service_add"
    assert "nuevo servicio" in respuesta["response"].lower()


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
    assert "Agregar servicio" in respuesta["messages"][1]["response"]
    assert "Eliminar servicio" in respuesta["messages"][1]["response"]


def test_confirmacion_agregar_servicios_persiste_y_regresa_a_menu(monkeypatch):
    async def _actualizar_servicios(proveedor_id, servicios):
        return servicios

    monkeypatch.setattr(
        modulo_gestor_servicios,
        "actualizar_servicios",
        _actualizar_servicios,
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

    assert flujo["state"] == "awaiting_service_action"
    assert flujo["services"] == [
        "desarrollo de software",
        "transporte terrestre nacional de carga",
    ]
    assert (
        "transporte terrestre nacional de carga" in respuesta["messages"][0]["response"]
    )


def test_confirmacion_agregar_servicios_con_siete_registrados_informa_limite():
    flujo = {
        "services": [f"servicio {idx}" for idx in range(1, 8)],
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

    assert flujo["state"] == "awaiting_service_action"
    assert (
        "ya tienes 7 servicios registrados"
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
            menu_limitado=False,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "awaiting_experience"
    assert "años de experiencia general" in respuesta["messages"][0]["response"].lower()


def test_menu_completar_perfil_reusa_servicios_existentes():
    flujo = {"services": ["plomeria"], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="completar perfil",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert flujo["profile_completion_mode"] is True
    assert flujo["state"] == "awaiting_experience"
    assert flujo["servicios_temporales"] == ["plomeria"]
    assert "años de experiencia" in respuesta["messages"][0]["response"].lower()


def test_menu_approved_basic_solo_muestra_opcion_completar_perfil():
    flujo = {"services": [], "approved_basic": True}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="2",
            opcion_menu="2",
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert "Completar perfil profesional" in respuesta["messages"][1]["response"]
    assert "Gestionar servicios" not in respuesta["messages"][1]["response"]


def test_menu_aprobado_abre_submenu_informacion_personal():
    flujo = {"services": ["plomeria"], "approved_basic": False}

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="provider_menu_info_personal",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert flujo["state"] == "awaiting_personal_info_action"
    assert respuesta["messages"][0]["ui"]["type"] == "list"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == "provider_submenu_personal_nombre"


def test_submenu_personal_nombre_inicia_actualizacion():
    flujo = {"approved_basic": False}

    respuesta = asyncio.run(
        manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje="provider_submenu_personal_nombre",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "awaiting_name"
    assert flujo["profile_edit_mode"] == "personal_name"
    assert "nombre completo" in respuesta["messages"][0]["response"].lower()


def test_submenu_personal_foto_no_se_interpreta_como_opcion_dos():
    texto = "provider_submenu_personal_foto"
    flujo = {"state": "awaiting_personal_info_action", "approved_basic": False}

    respuesta = asyncio.run(
        enrutar_estado(
            estado=flujo["state"],
            flujo=flujo,
            texto_mensaje=texto,
            carga={"selected_option": texto},
            telefono="593999111200@s.whatsapp.net",
            opcion_menu=interpretar_respuesta(texto, "menu"),
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

    assert flujo["state"] == "awaiting_face_photo_update"
    assert "foto de perfil" in respuesta["response"]["messages"][0]["response"].lower()


def test_submenu_profesional_certificado_inicia_reemplazo():
    flujo = {"approved_basic": False}

    respuesta = asyncio.run(
        manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje="provider_submenu_profesional_certificados",
            opcion_menu=None,
        )
    )

    assert flujo["state"] == "awaiting_certificate"
    assert flujo["profile_edit_mode"] == "provider_certificate_update"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"


def test_actualizacion_nombre_regresa_menu_interactivo(monkeypatch):
    async def _actualizar_nombre_proveedor(_supabase, _proveedor_id, nombre):
        return {"success": True, "full_name": nombre.title()}

    monkeypatch.setattr(
        "flows.gestores_estados.gestor_espera_nombre.actualizar_nombre_proveedor",
        _actualizar_nombre_proveedor,
    )

    flujo = {
        "state": "awaiting_name",
        "profile_edit_mode": "personal_name",
        "menu_limitado": False,
        "approved_basic": False,
    }

    respuesta = asyncio.run(
        manejar_espera_nombre(
            flujo,
            "maria lopez",
            supabase=object(),
            proveedor_id="prov-1",
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert respuesta["messages"][1]["ui"]["type"] == "list"
    assert respuesta["messages"][1]["ui"]["options"][0]["id"] == "provider_menu_info_personal"


def test_completar_perfil_envia_a_revision_humana(monkeypatch):
    async def _actualizar_perfil_profesional(**kwargs):
        return {"success": True}

    async def _agregar_certificado_proveedor(**kwargs):
        return {"success": True}

    monkeypatch.setattr("flows.router.actualizar_perfil_profesional", _actualizar_perfil_profesional)
    monkeypatch.setattr("flows.router.agregar_certificado_proveedor", _agregar_certificado_proveedor)

    flujo = {
        "state": "awaiting_profile_completion_confirmation",
        "approved_basic": True,
        "profile_completion_mode": True,
        "menu_limitado": False,
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

    assert flujo["approved_basic"] is False
    assert flujo["profile_pending_review"] is True
    assert flujo["state"] == "pending_verification"
    assert len(respuesta["response"]["messages"]) == 1
    assert "revisando" in respuesta["response"]["messages"][0]["response"].lower()
    assert (
        "clientes que realmente necesitan tus servicios"
        in respuesta["response"]["messages"][0]["response"].lower()
    )


def test_confirmacion_servicios_exige_minimo_tres_en_perfil():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial", "deteccion de fugas"],
        "state": "awaiting_services_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="1",
            cliente_openai=None,
        )
    )

    assert flujo["state"] == "awaiting_services_confirmation"
    assert "al menos *3 servicios*" in respuesta["messages"][0]["response"].lower()


def test_decision_no_continuar_exige_minimo_tres_en_perfil():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial", "deteccion de fugas"],
        "state": "awaiting_add_another_service",
    }

    respuesta = asyncio.run(
        manejar_decision_agregar_otro_servicio(
            flujo=flujo,
            texto_mensaje="profile_add_another_service_no",
        )
    )

    assert flujo["state"] == "awaiting_specialty"
    assert "al menos *3 servicios*" in respuesta["messages"][0]["response"].lower()
    assert "3/3" in respuesta["messages"][1]["response"].lower()


def test_certificado_omitido_avanza_a_servicios():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial"],
        "provider_id": "prov-1",
        "state": "awaiting_certificate",
    }

    respuesta = asyncio.run(
        manejar_espera_certificado(
            flujo=flujo,
            carga={"selected_option": "skip_profile_certificate"},
        )
    )

    assert flujo["state"] == "awaiting_specialty"
    assert "2/3" in respuesta["messages"][0]["response"].lower()
    assert "ahora sí, vamos con tus servicios" not in respuesta["messages"][0]["response"].lower()


def test_control_viejo_no_se_interpreta_como_servicio():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": ["plomeria residencial"],
        "state": "awaiting_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="skip_profile_certificate",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_specialty"
    assert "2/3" in respuesta["messages"][0]["response"]


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

    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": [],
        "state": "awaiting_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="desarrollo de software con ia",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "awaiting_profile_service_confirmation"
    assert flujo["pending_service_candidate"] == "desarrollo aplicaciones moviles inteligencia artificial"
    assert "servicio 1 de 3 identificado" in respuesta["messages"][0]["response"].lower()


def test_confirmar_servicio_perfil_avanza_al_siguiente_paso():
    flujo = {
        "profile_completion_mode": True,
        "servicios_temporales": [],
        "pending_service_candidate": "desarrollo aplicaciones moviles inteligencia artificial",
        "pending_service_index": 0,
        "state": "awaiting_profile_service_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje="",
            selected_option="profile_service_confirm",
        )
    )

    assert flujo["state"] == "awaiting_specialty"
    assert flujo["servicios_temporales"] == [
        "desarrollo aplicaciones moviles inteligencia artificial"
    ]
    assert "2/3" in respuesta["messages"][0]["response"].lower()


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
        "state": "awaiting_profile_service_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje="",
            selected_option="profile_service_confirm",
        )
    )

    assert flujo["state"] == "awaiting_profile_completion_confirmation"
    assert "por favor confirma tus datos" in respuesta["messages"][0]["response"].lower()
    assert "servicio 1" in respuesta["messages"][0]["response"].lower()
    assert "servicio 3" in respuesta["messages"][0]["response"].lower()


def test_no_acepto_abre_menu_edicion_integral():
    flujo = {
        "profile_completion_mode": True,
        "experience_years": 5,
        "social_media_url": None,
        "certificate_uploaded": False,
        "servicios_temporales": ["servicio 1", "servicio 2", "servicio 3"],
        "state": "awaiting_profile_completion_confirmation",
    }

    respuesta = asyncio.run(
        manejar_confirmacion_perfil_profesional(
            flujo=flujo,
            texto_mensaje="",
            selected_option="confirm_reject",
        )
    )

    assert flujo["state"] == "awaiting_profile_completion_edit_action"
    assert "qué deseas corregir" in respuesta["messages"][0]["response"].lower()
