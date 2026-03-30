import asyncio
import json
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
from flows.maintenance.services import (  # noqa: E402
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
)
from flows.maintenance.services_confirmation import (  # noqa: E402
    manejar_accion_edicion_servicios_registro,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
)
from flows.maintenance.specialty import (  # noqa: E402
    manejar_espera_especialidad,
    normalizar_servicio_registro_individual,
)
from flows.onboarding.handlers.experiencia import (  # noqa: E402
    manejar_espera_experiencia_onboarding,
)
from flows.onboarding.handlers.servicios import (  # noqa: E402
    manejar_decision_agregar_otro_servicio_onboarding,
    manejar_espera_servicios_onboarding,
    resolver_servicio_onboarding_best_effort,
)
from flows.onboarding.router import manejar_estado_onboarding  # noqa: E402
from flows.validators.name import validar_nombre_completo  # noqa: E402
from infrastructure.openai import (  # noqa: E402
    transformador_servicios as modulo_transformador,
)
from services.maintenance import (  # noqa: E402
    clasificacion_semantica as modulo_clasificacion,
)
from services.maintenance.asistente_clarificacion import (  # noqa: E402
    construir_mensaje_clarificacion_servicio,
)
from services.maintenance.validacion_semantica import (  # noqa: E402
    validar_servicio_semanticamente,
)
from templates.maintenance import (  # noqa: E402
    mensaje_correccion_servicios,
)
from templates.onboarding import (  # noqa: E402
    payload_servicios_onboarding_con_imagen,
    preguntar_servicios_onboarding,
)
from utils import (  # noqa: E402
    dividir_cadena_servicios,
    normalizar_texto_visible_con_ia,
    normalizar_texto_visible_corto,
    parsear_servicios_numerados_con_limite,
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


@pytest.mark.asyncio
async def test_transformador_servicios_separa_y_limpia_sin_ai():
    transformador = modulo_transformador.TransformadorServicios(cliente_openai=object())

    servicios = await transformador.transformar_a_servicios(
        "plomería; electricidad / jardinería",
        max_servicios=7,
    )

    assert servicios == ["plomería", "electricidad", "jardinería"]
    assert modulo_transformador._crear_prompt_sistema()


def test_prompt_servicios_onboarding_usa_formato_compacto():
    mensaje = preguntar_servicios_onboarding()

    assert mensaje == (
        "*Describe el servicio que ofreces*\n\n"
        "Escribe solo un servicio por mensaje. "
        "Mientras más claro y detallado sea, mejor podremos clasificarlo."
    )
    assert "Servicio guardado." not in mensaje


def test_prompt_servicios_onboarding_usa_env_override(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SERVICES_IMAGE_URL",
        "https://example.com/services-image.png",
    )

    respuesta = payload_servicios_onboarding_con_imagen()

    assert respuesta["media_type"] == "image"
    assert respuesta["media_url"] == "https://example.com/services-image.png"


@pytest.mark.asyncio
async def test_onboarding_servicios_captura_texto_crudo_sin_llamar_openai(monkeypatch):
    async def _no_deberia_llamarse(**_kwargs):
        raise AssertionError("No debe usar OpenAI en el request path")

    monkeypatch.setitem(
        manejar_espera_servicios_onboarding.__globals__,
        "normalizar_servicios_onboarding",
        _no_deberia_llamarse,
    )

    flujo = {"state": "onboarding_specialty", "servicios_temporales": []}

    respuesta = await manejar_espera_servicios_onboarding(
        flujo=flujo,
        texto_mensaje="Gestion de proyectos de tics",
        cliente_openai=object(),
    )

    assert flujo["state"] == "onboarding_add_another_service"
    assert flujo["servicios_temporales"] == ["Gestion de proyectos de tics"]
    assert (
        flujo["service_entries"][0]["raw_service_text"]
        == "Gestion de proyectos de tics"
    )
    assert flujo["service_entries"][0]["requires_review"] is True
    assert (
        respuesta["messages"][0]["ui"]["header_text"]
        == "¿Quieres agregar otro servicio?"
    )


@pytest.mark.asyncio
async def test_resolver_servicio_best_effort_hace_fallback_a_texto_crudo(monkeypatch):
    async def _falla_normalizacion(**_kwargs):
        return {"ok": False, "response": "No pude interpretar ese servicio."}

    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "normalizar_servicios_onboarding",
        _falla_normalizacion,
    )

    resultado = await resolver_servicio_onboarding_best_effort(
        texto_mensaje="Servicio raro inventado",
        cliente_openai=object(),
    )

    assert resultado["ok"] is True
    assert resultado["used_fallback"] is True
    assert resultado["service_detail"]["service_name"] == "Servicio raro inventado"
    assert resultado["service_detail"]["requires_review"] is True


@pytest.mark.asyncio
async def test_resolver_servicio_best_effort_registra_review_catalogo(
    monkeypatch,
):
    captured = {}

    async def _fake_normalizar(**_kwargs):
        return {
            "ok": True,
            "service_detail": {
                "raw_service_text": "Gestion de proyectos tics",
                "service_name": "Gestión de proyectos TIC",
                "service_summary": "Gestión de proyectos relacionados con tecnologías de la información.",
                "domain_code": None,
                "category_name": None,
                "classification_confidence": 0.52,
                "requires_review": True,
                "review_reason": "catalog_review_required",
            },
        }

    async def _fake_registrar_revision_catalogo_servicio(**kwargs):
        captured.update(kwargs)
        return {"id": "review-1"}

    async def _fake_sugerencia_revision_catalogo_servicio(**_kwargs):
        return {
            "suggested_domain_code": "tecnologia",
            "proposed_category_name": "Servicios tecnológicos",
            "proposed_service_summary": "Gestión de proyectos tecnológicos con foco en IA.",
            "review_reason": "best_effort_catalog_suggestion",
            "confidence": 0.84,
        }

    async def _fake_obtener_catalogo_dominios_liviano(_supabase):
        return [{"code": "tecnologia", "display_name": "Tecnología", "description": ""}]

    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "normalizar_servicios_onboarding",
        _fake_normalizar,
    )
    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "registrar_revision_catalogo_servicio",
        _fake_registrar_revision_catalogo_servicio,
    )
    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "generar_sugerencia_revision_catalogo_servicio",
        _fake_sugerencia_revision_catalogo_servicio,
    )
    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "obtener_catalogo_dominios_liviano",
        _fake_obtener_catalogo_dominios_liviano,
    )
    monkeypatch.setitem(
        resolver_servicio_onboarding_best_effort.__globals__,
        "_resolver_supabase_runtime",
        lambda: object(),
    )

    resultado = await resolver_servicio_onboarding_best_effort(
        texto_mensaje="Gestion de proyectos tics",
        cliente_openai=object(),
        provider_id="prov-1",
    )

    assert resultado["ok"] is True
    assert captured["provider_id"] == "prov-1"
    assert captured["raw_service_text"] == "Gestion de proyectos tics"
    assert captured["service_name"] == "Gestión de proyectos TIC"
    assert captured["suggested_domain_code"] == "tecnologia"
    assert captured["proposed_category_name"] == "Servicios tecnológicos"
    assert captured["review_reason"] == "best_effort_catalog_suggestion"
    assert captured["source"] == "provider_onboarding"


@pytest.mark.asyncio
async def test_onboarding_experiencia_solo_primera_vez_muestra_imagen(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SERVICES_IMAGE_URL",
        "https://example.com/services-image.png",
    )

    flujo = {"state": "onboarding_experience"}

    respuesta = await manejar_espera_experiencia_onboarding(
        flujo=flujo,
        texto_mensaje="5",
    )

    assert flujo["state"] == "onboarding_specialty"
    assert flujo["services_guide_shown"] is True
    assert respuesta["messages"][0]["media_type"] == "image"
    assert respuesta["messages"][0]["media_url"] == (
        "https://example.com/services-image.png"
    )


@pytest.mark.asyncio
async def test_onboarding_agregar_otro_servicio_va_sin_imagen(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SERVICES_IMAGE_URL",
        "https://example.com/services-image.png",
    )

    flujo = {
        "state": "onboarding_add_another_service",
        "services_guide_shown": True,
        "servicios_temporales": ["instalaciones eléctricas"],
    }

    respuesta = await manejar_decision_agregar_otro_servicio_onboarding(
        flujo=flujo,
        texto_mensaje="si",
    )

    assert flujo["state"] == "onboarding_specialty"
    assert respuesta["messages"][0]["response"].startswith(
        "*Describe el servicio que ofreces*"
    )
    assert "media_type" not in respuesta["messages"][0]
    assert "media_url" not in respuesta["messages"][0]


@pytest.mark.asyncio
async def test_router_onboarding_nuevo_enruta_servicios_compactos(monkeypatch):
    async def _fake_handler(**_kwargs):
        return {
            "success": True,
            "messages": [{"response": "ok onboarding nuevo"}],
        }

    monkeypatch.setattr(
        "flows.onboarding.router.manejar_espera_servicios_onboarding",
        _fake_handler,
    )

    respuesta = await manejar_estado_onboarding(
        estado="onboarding_specialty",
        flujo={"mode": "registration"},
        telefono="593999111200@s.whatsapp.net",
        texto_mensaje="1 albañilería 2 plomería",
        carga={},
        supabase=None,
    )

    assert respuesta["success"] is True
    assert respuesta["messages"][0]["response"] == "ok onboarding nuevo"


@pytest.mark.asyncio
async def test_handler_onboarding_experiencia_avanza_a_servicios():
    flujo = {"state": "onboarding_experience"}

    respuesta = await manejar_espera_experiencia_onboarding(
        flujo=flujo,
        texto_mensaje="3",
        selected_option="provider_experience_3_5",
    )

    assert flujo["state"] == "onboarding_specialty"
    assert respuesta["messages"][0]["media_type"] == "image"


def test_parsear_servicios_numerados_con_limite_extrae_bloque_continuo():
    servicios = parsear_servicios_numerados_con_limite(
        "1 Albañilería general 2 Plomería y fontanería 3 Jardinería y poda de árboles",
        maximos=7,
    )

    assert servicios == [
        "Albañilería general",
        "Plomería y fontanería",
        "Jardinería y poda de árboles",
    ]


def test_parsear_servicios_numerados_con_limite_rechaza_bloque_sin_numeros():
    servicios = parsear_servicios_numerados_con_limite(
        "Albañilería general, plomería y fontanería, jardinería y poda de árboles",
        maximos=7,
    )

    assert servicios == []


def test_parsear_servicios_numerados_con_limite_recorta_a_siete():
    servicios = parsear_servicios_numerados_con_limite(
        (
            "1 Servicio uno 2 Servicio dos 3 Servicio tres 4 Servicio cuatro "
            "5 Servicio cinco 6 Servicio seis 7 Servicio siete 8 Servicio ocho"
        ),
        maximos=7,
    )

    assert servicios == [
        "Servicio uno",
        "Servicio dos",
        "Servicio tres",
        "Servicio cuatro",
        "Servicio cinco",
        "Servicio seis",
        "Servicio siete",
    ]


@pytest.mark.asyncio
async def test_espera_experiencia_onboarding_muestra_lista_de_ejemplos():
    flujo = {"state": "onboarding_experience"}

    respuesta = await manejar_espera_experiencia_onboarding(
        flujo=flujo,
        texto_mensaje="3",
        selected_option="provider_experience_3_5",
    )

    assert flujo["state"] == "onboarding_specialty"
    assert flujo["experience_range"] == "3 a 5 años"
    assert respuesta["messages"][0]["media_type"] == "image"
    assert "tinkubot_add_services.png" in respuesta["messages"][0]["media_url"]
    assert respuesta["messages"][0]["response"] == (
        "*Describe el servicio que ofreces*\n\n"
        "Escribe solo un servicio por mensaje. "
        "Mientras más claro y detallado sea, mejor podremos clasificarlo."
    )


def test_validar_nombre_completo_rechaza_entrada_incompleta():
    respuesta = validar_nombre_completo("juan")

    assert respuesta["is_valid"] is False
    assert respuesta["reason"] == "too_short"
    assert "nombre y apellido" in respuesta["message"].lower()


def test_validar_nombre_completo_rechaza_texto_generico():
    respuesta = validar_nombre_completo("omitir")

    assert respuesta["is_valid"] is False
    assert respuesta["reason"] == "blocked"
    assert "nombre y apellido" in respuesta["message"].lower()


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
            "Desarrollo de software; configuracion de redes e internet; "
            "servicios de cableado estructurado"
        ),
    )

    assert servicios == [
        "desarrollo de software",
        "configuracion de redes e internet",
        "cableado estructurado",
    ]


def test_dividir_cadena_servicios_no_separa_por_coma_simple():
    servicios = dividir_cadena_servicios(
        "diseño y configuración de equipos de red de comunicaciones, "
        "con soporte técnico"
    )

    assert servicios == [
        (
            "diseño y configuración de equipos de red de comunicaciones, "
            "con soporte técnico"
        )
    ]


def test_dividir_cadena_servicios_separa_por_punto_y_coma():
    servicios = dividir_cadena_servicios(
        "diseño y configuración de equipos de red de comunicaciones; "
        "con soporte técnico"
    )

    assert servicios == [
        "diseño y configuración de equipos de red de comunicaciones",
        "con soporte técnico",
    ]


def test_normalizador_texto_visible_prefiere_corte_semantico():
    texto = normalizar_texto_visible_corto(
        "Automatizacion de procesos con software e IA, "
        "incluye soporte tecnico especializado y mantenimiento continuo"
    )

    assert texto == "Automatizacion de procesos con software e IA"
    assert len(texto) <= 68


def test_normalizador_texto_visible_con_ia_reintenta_hasta_cumplir_limite():
    class _Respuesta:
        def __init__(self, content):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    class _Completions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                payload = {
                    "normalized_service": (
                        "Automatizacion de procesos con software e IA, "
                        "incluye soporte tecnico especializado y mantenimiento continuo"
                    )
                }
            else:
                payload = {
                    "normalized_service": "Automatizacion de procesos con software e IA"
                }
            return _Respuesta(json.dumps(payload))

    completions = _Completions()
    cliente_openai = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    texto = asyncio.run(
        normalizar_texto_visible_con_ia(
            cliente_openai,
            "Automatizacion de procesos con software e IA, "
            "incluye soporte tecnico especializado y mantenimiento continuo",
        )
    )

    assert texto == "Automatizacion de procesos con software e IA"
    assert completions.calls == 2


def test_validar_servicio_semanticamente_recorta_normalized_service_visible():
    class _Respuesta:
        def __init__(self, content):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    class _Completions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                payload = {
                    "status": "catalog_review_required",
                    "normalized_service": (
                        "instalación y mantenimiento de sistemas de climatización "
                        "industrial para grandes superficies y complejos empresariales"
                    ),
                    "domain_code": "mantenimiento",
                    "category_name": "climatización",
                    "service_summary": (
                        "Instalo y mantengo sistemas de climatización industrial "
                        "para grandes superficies."
                    ),
                    "confidence": 0.91,
                    "reason": "ai_validation",
                    "clarification_question": None,
                }
            else:
                payload = {
                    "normalized_service": (
                        "instalación y mantenimiento de sistemas de climatización "
                        "industrial"
                    )
                }
            return _Respuesta(json.dumps(payload))

    class _Chat:
        completions = _Completions()

    class _ClienteOpenAI:
        chat = _Chat()

    cliente_openai = _ClienteOpenAI()

    resultado = asyncio.run(
        validar_servicio_semanticamente(
            cliente_openai=cliente_openai,
            supabase=None,
            raw_service_text=(
                "instalación y mantenimiento de sistemas de climatización industrial"
            ),
            service_name=(
                "instalación y mantenimiento de sistemas de climatización industrial"
            ),
        )
    )

    assert len(resultado["normalized_service"]) <= 68
    assert "…" not in resultado["normalized_service"]
    assert cliente_openai.chat.completions.calls == 1


def test_espera_especialidad_onboarding_con_linea_numerada_va_a_consentimiento(
    monkeypatch,
):
    class _TransformadorLinea:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            entrada = entrada_usuario.lower()
            if "desarrollo web" in entrada:
                return ["desarrollo web"]
            if "mantenimiento de software" in entrada:
                return ["mantenimiento de software"]
            if "soporte tecnico" in entrada or "soporte técnico" in entrada:
                return ["soporte tecnico"]
            return [entrada_usuario]

    async def _fake_validar_servicio_semanticamente(**kwargs):
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
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorLinea,
    )
    monkeypatch.setattr(
        "flows.maintenance.specialty.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )
    flujo = {"state": "onboarding_specialty"}

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje=(
                "1 desarrollo web 2 mantenimiento de software 3 soporte tecnico"
            ),
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_services_confirmation"
    assert flujo["servicios_temporales"] == [
        "desarrollo web",
        "mantenimiento de software",
        "soporte tecnico",
    ]
    assert (
        respuesta["messages"][0]["ui"]["header_text"]
        == "Resumen de servicios identificados"
    )
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Continuar"
    assert respuesta["messages"][0]["ui"]["options"][1]["title"] == "Corregir"
    assert (
        "¿Estás de acuerdo con esta lista?" not in respuesta["messages"][0]["response"]
    )


def test_espera_especialidad_onboarding_rechaza_multiservicio_sin_numeros(
    monkeypatch,
):
    class _TransformadorLinea:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            return [entrada_usuario]

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorLinea,
    )

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo={"state": "onboarding_specialty"},
            texto_mensaje=(
                "Albañilería general, plomería y fontanería, "
                "jardinería y poda de árboles"
            ),
            cliente_openai=object(),
        )
    )

    assert respuesta["messages"][0]["response"] == (
        "Escribe el servicio con el mayor detalle posible. "
        "Si necesitas, sepáralo por coma o en una línea distinta."
    )


def test_confirmacion_servicio_onboarding_avanza_al_siguiente_servicio(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorOK,
    )

    async def _fake_validar_servicio_semanticamente(**_kwargs):
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": "desarrollo web",
            "domain_resolution_status": "matched",
            "domain_code": "tecnologia",
            "resolved_domain_code": "tecnologia",
            "proposed_category_name": "desarrollo web",
            "proposed_service_summary": "Desarrollo de sitios y aplicaciones web.",
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.maintenance.specialty.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )

    flujo = {
        "state": "onboarding_specialty",
        "servicios_temporales": [],
        "profile_completion_mode": True,
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="desarrollo web",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_profile_service_confirmation"

    respuesta = asyncio.run(
        manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje="",
            selected_option="profile_service_confirm",
        )
    )

    assert flujo["state"] == "pending_verification"
    assert flujo["servicios_temporales"] == ["desarrollo web"]
    assert respuesta["success"] is True
    assert respuesta["messages"][0]["response"]
    assert "revisión" in respuesta["messages"][0]["response"].lower()


def test_confirmacion_tercer_servicio_onboarding_va_a_consentimiento():
    flujo = {
        "servicios_temporales": ["servicio 1", "servicio 2"],
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
    assert flujo["servicios_temporales"] == [
        "servicio 1",
        "servicio 2",
        "servicio 3",
    ]
    assert "en revisión" in respuesta["messages"][0]["response"].lower()


def test_espera_especialidad_onboarding_con_tres_servicios_va_a_consentimiento(
    monkeypatch,
):
    class _TransformadorExtra:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=1):
            return ["servicio extra"]

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": "general",
            "resolved_domain_code": "general",
            "proposed_category_name": servicio,
            "proposed_service_summary": f"Servicio de {servicio}.",
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorExtra,
    )
    monkeypatch.setattr(
        "flows.maintenance.specialty.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )
    flujo = {
        "servicios_temporales": [
            "servicio 1",
            "servicio 2",
            "servicio 3",
        ],
        "state": "onboarding_specialty",
    }

    respuesta = asyncio.run(
        manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje="1 servicio extra",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_services_confirmation"
    assert flujo["specialty"] == "servicio 1, servicio 2, servicio 3, servicio extra"
    assert (
        respuesta["messages"][0]["ui"]["header_text"]
        == "Resumen de servicios identificados"
    )
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Continuar"
    assert respuesta["messages"][0]["ui"]["options"][1]["title"] == "Corregir"
    assert (
        "¿Estás de acuerdo con esta lista?" not in respuesta["messages"][0]["response"]
    )


def test_normalizacion_servicio_pide_aclaracion_en_lugar_de_revision(monkeypatch):
    class _TransformadorPaneles:
        def __init__(self, cliente_openai, modelo=None):
            self.cliente_openai = cliente_openai
            self.modelo = modelo

        async def transformar_a_servicios(self, entrada_usuario, max_servicios=7):
            return ["instalación de paneles solares"]

    async def _fake_validar_servicio_semanticamente(**_kwargs):
        proposed_summary = "Instalo paneles solares para hogares " "y negocios."
        return {
            "is_valid_service": True,
            "needs_clarification": True,
            "normalized_service": "instalación de paneles solares",
            "domain_resolution_status": "clarification_required",
            "domain_code": "energia_renovable",
            "resolved_domain_code": None,
            "proposed_category_name": "instalación de paneles solares",
            "proposed_service_summary": proposed_summary,
            "reason": "catalog_gap_detected",
            "clarification_question": (
                "Indica el tipo de instalación exacta que realizas."
            ),
        }

    async def _fake_construir_mensaje_clarificacion_servicio(**_kwargs):
        return {
            "message": (
                "Indica el tipo de instalación exacta que realizas.\n\n"
                "Para ayudarte a aterrizarlo, estos servicios reales se parecen:\n"
                "1 Instalación de paneles solares - Energía solar y fotovoltaica.\n"
                "2 Mantenimiento de paneles solares - Limpieza y soporte técnico.\n"
                "3 Instalación eléctrica residencial - Electricidad para hogares.\n\n"
                "Respóndeme con una versión más específica."
            )
        }

    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorPaneles,
    )
    monkeypatch.setattr(
        "flows.maintenance.specialty.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )
    monkeypatch.setattr(
        "flows.maintenance." "specialty." "construir_mensaje_clarificacion_servicio",
        _fake_construir_mensaje_clarificacion_servicio,
    )

    respuesta = asyncio.run(
        normalizar_servicio_registro_individual(
            texto_mensaje="instalacion de paneles solares",
            cliente_openai=object(),
            servicio_embeddings=object(),
        )
    )

    assert respuesta["ok"] is False
    assert respuesta["needs_clarification"] is True
    assert "Instalación de paneles solares" in respuesta["response"]
    assert "Respóndeme con una versión más específica" in respuesta["response"]


def test_asistente_clarificacion_usa_ejemplos_reales(monkeypatch):
    class _EmbeddingServicio:
        async def generar_embedding(self, texto):
            assert "asesoria legal" in texto.lower()
            return [0.2, 0.4, 0.6]

    class _RpcQuery:
        def execute(self):
            return SimpleNamespace(
                data=[
                    {
                        "matched_service_name": "Asesoría en derecho laboral",
                        "matched_service_summary": (
                            "Brindo asesoría en despidos, contratos " "y liquidaciones."
                        ),
                        "domain_code": "legal",
                        "category_name": "derecho laboral",
                        "distance": 0.12,
                    },
                    {
                        "matched_service_name": "Asesoría en derecho de familia",
                        "matched_service_summary": (
                            "Acompaño trámites de familia y pensiones."
                        ),
                        "domain_code": "legal",
                        "category_name": "derecho de familia",
                        "distance": 0.18,
                    },
                ]
            )

    class _SupabaseStub:
        def rpc(self, fn_name, params):
            assert fn_name == "match_provider_services"
            assert params["match_count"] >= 8
            return _RpcQuery()

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    monkeypatch.setattr(
        "services.maintenance.asistente_clarificacion.run_supabase",
        _fake_run_supabase,
    )

    respuesta = asyncio.run(
        construir_mensaje_clarificacion_servicio(
            supabase=_SupabaseStub(),
            servicio_embeddings=_EmbeddingServicio(),
            raw_service_text="asesoria legal de familia",
            service_name="asesoria legal de familia",
            clarification_question=(
                "Indica el trámite o área legal exacta " "que trabajas."
            ),
        )
    )

    assert "Asesoría en derecho laboral" in respuesta["message"]
    assert "Asesoría en derecho de familia" in respuesta["message"]
    assert "Indica el trámite o área legal exacta" in respuesta["message"]


def test_decision_agregar_otro_no_pasa_a_resumen_final():
    flujo = {
        "state": "onboarding_add_another_service",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(
        "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL",
        "https://example.com/social-network.png",
    )
    try:
        respuesta = asyncio.run(
            manejar_decision_agregar_otro_servicio_onboarding(
                flujo=flujo,
                texto_mensaje="2",
            )
        )
    finally:
        monkeypatch.undo()

    assert flujo["state"] == "onboarding_social_media"
    assert respuesta["messages"][0]["ui"]["header_type"] == "image"
    assert respuesta["messages"][0]["ui"]["header_media_url"] == (
        "https://example.com/social-network.png"
    )


def test_confirmacion_agregar_servicios_re_normaliza_correccion_manual(monkeypatch):
    monkeypatch.setattr(modulo_services, "TransformadorServicios", _TransformadorOK)

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": "construccion_hogar",
            "resolved_domain_code": "construccion_hogar",
            "proposed_category_name": servicio,
            "proposed_service_summary": f"Servicio de {servicio}.",
            "service_summary": f"Servicio de {servicio}.",
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.maintenance.services.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
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
            texto_mensaje="plomero para destapar lavamanos",
            cliente_openai=object(),
        )
    )

    assert flujo["state"] == "maintenance_service_add_confirmation"
    assert flujo["service_add_temporales"] == ["plomería"]
    assert "plomería" in respuesta["messages"][0]["response"]


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
            flujo={"state": "onboarding_specialty"},
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
    assert "No pude interpretar ese servicio" in resultado["response"]


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

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        proposed_summary = "Brindo asesoría en temas legales."
        return {
            "is_valid_service": True,
            "needs_clarification": True,
            "normalized_service": servicio,
            "domain_resolution_status": "clarification_required",
            "domain_code": "legal",
            "resolved_domain_code": None,
            "proposed_category_name": servicio,
            "proposed_service_summary": proposed_summary,
            "service_summary": proposed_summary,
            "reason": "generic_service",
            "clarification_question": (
                "Indica el trámite o área legal exacta " "con la que trabajas."
            ),
        }

    monkeypatch.setattr(
        "flows.maintenance.specialty.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
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

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        dominio = "transporte" if "barco" not in servicio else "transporte"
        proposed_summary = f"Servicio de {servicio}."
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": dominio,
            "resolved_domain_code": dominio,
            "proposed_category_name": servicio,
            "proposed_service_summary": proposed_summary,
            "service_summary": proposed_summary,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.onboarding.handlers.servicios.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
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
        "state": "maintenance_services_confirmation",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="1",
        )
    )

    assert flujo["state"] == "pending_verification"
    assert flujo["specialty"] == "desarrollo web, cableado estructurado"
    assert "revisión" in respuesta["messages"][0]["response"].lower()


def test_confirmacion_servicios_abre_menu_edicion():
    flujo = {
        "state": "maintenance_services_confirmation",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje="2",
        )
    )

    assert flujo["state"] == "maintenance_services_edit_action"
    assert "¿Qué deseas corregir?" in respuesta["messages"][1]["response"]


def test_reemplazo_servicio_en_edicion(monkeypatch):
    monkeypatch.setattr(
        modulo_transformador,
        "TransformadorServicios",
        _TransformadorOK,
    )

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        proposed_summary = f"Servicio de {servicio}."
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": "legal",
            "resolved_domain_code": "legal",
            "proposed_category_name": servicio,
            "proposed_service_summary": proposed_summary,
            "service_summary": proposed_summary,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.onboarding.handlers.servicios.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )
    flujo = {
        "state": "maintenance_services_edit_action",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta_select = asyncio.run(
        manejar_accion_edicion_servicios_registro(flujo, "1")
    )
    assert flujo["state"] == "maintenance_services_edit_replace_select"
    assert "reemplazar" in respuesta_select["messages"][1]["response"].lower()

    respuesta_indice = asyncio.run(
        manejar_seleccion_reemplazo_servicio_registro(flujo, "2")
    )
    assert flujo["state"] == "maintenance_services_edit_replace_input"
    assert "servicio 2" in respuesta_indice["messages"][0]["response"].lower()

    respuesta_reemplazo = asyncio.run(
        manejar_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje="abogado para rebaja de pensión alimenticia",
            cliente_openai=object(),
        )
    )
    assert flujo["state"] == "maintenance_services_confirmation"
    assert flujo["servicios_temporales"] == [
        "desarrollo web",
        "asesoría para rebaja de pensión alimenticia",
    ]
    assert "Servicio actualizado" in respuesta_reemplazo["messages"][0]["response"]


def test_eliminacion_servicio_en_edicion():
    flujo = {
        "state": "maintenance_services_edit_delete_select",
        "servicios_temporales": ["desarrollo web", "cableado estructurado"],
    }

    respuesta = asyncio.run(
        manejar_eliminacion_servicio_registro(
            flujo=flujo,
            texto_mensaje="1",
        )
    )

    assert flujo["state"] == "maintenance_services_confirmation"
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
        modulo_services, "TransformadorServicios", _TransformadorGenerico
    )

    async def _fake_validar_servicio_semanticamente(**kwargs):
        servicio = kwargs["service_name"]
        proposed_summary = f"Servicio de {servicio}."
        return {
            "is_valid_service": True,
            "needs_clarification": False,
            "normalized_service": servicio,
            "domain_resolution_status": "matched",
            "domain_code": "transporte",
            "resolved_domain_code": "transporte",
            "proposed_category_name": servicio,
            "proposed_service_summary": proposed_summary,
            "service_summary": proposed_summary,
            "reason": "heuristic_accept",
            "clarification_question": None,
        }

    monkeypatch.setattr(
        "flows.maintenance.services.validar_servicio_semanticamente",
        _fake_validar_servicio_semanticamente,
    )

    respuesta = asyncio.run(
        manejar_agregar_servicios(
            flujo={"state": "maintenance_service_add", "services": []},
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
            "desarrollo de software a medida; automatizacion de procesos de negocio; "
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
        modulo_clasificacion.normalizar_domain_code_operativo(
            "servicios administrativos"
        )
        == "servicios_administrativos"
    )


def test_normalizacion_display_name_dominio_reduce_dominios_largos():
    assert (
        modulo_clasificacion.normalizar_display_name_dominio(
            "servicios_administrativos"
        )
        == "Administración"
    )
    assert (
        modulo_clasificacion.normalizar_display_name_dominio("gastronomia_alimentos")
        == "Gastronomía"
    )
    assert (
        modulo_clasificacion.normalizar_display_name_dominio("cuidados_asistencia")
        == "Cuidados"
    )
    assert (
        modulo_clasificacion.normalizar_display_name_dominio("construccion_hogar")
        == "Construcción"
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


def test_texto_embedding_canonico_usa_gramatica_estable():
    texto = modulo_clasificacion.construir_texto_embedding_canonico(
        service_name_normalized="Desarrollo de Software a Medida",
        domain_code="Tecnología",
        category_name="Servicios tecnológicos",
    )

    assert texto == (
        "desarrollo de software a medida | tecnologia | servicios tecnologicos"
    )


def test_reclasificacion_masiva_ignora_service_summary_en_embedding():
    from tools.maintenance import reclasificar_provider_services_masivo as modulo_reclasificar

    row = modulo_reclasificar.ProviderServiceRow(
        id="row-1",
        provider_id="prov-1",
        service_name="Desarrollo de software",
        raw_service_text="desarrollo de software",
        service_summary="Resumen previo",
        domain_code="tecnologia",
        category_name="Servicios tecnologicos",
        classification_confidence=0.93,
        service_embedding=[0.1, 0.2],
    )
    resolved = {
        "normalized_service": "Desarrollo de software",
        "resolved_domain_code": "tecnologia",
        "category_name": "Servicios tecnologicos",
        "service_summary": "Resumen distinto para UI",
        "confidence": 0.97,
    }

    payload, needs_embedding, accepted, embedding_text = modulo_reclasificar._build_update_payload(  # noqa: SLF001
        row=row,
        resolved=resolved,
        conflict_free_name_update=True,
    )

    assert embedding_text == modulo_clasificacion.construir_texto_embedding_canonico(
        service_name_normalized="Desarrollo de software",
        domain_code="tecnologia",
        category_name="Servicios tecnologicos",
    )
    assert needs_embedding is False
    assert payload["service_summary"] == "Resumen distinto para UI"
    assert accepted is True


@pytest.mark.asyncio
async def test_insertar_servicios_proveedor_usa_texto_embedding_canonico(monkeypatch):
    captured = {}

    async def _fake_run_supabase(operation, **_kwargs):
        return operation()

    async def _fake_clasificar_servicios_livianos(**_kwargs):
        return [
            {
                "resolved_domain_code": "tecnologia",
                "category_name": "Servicios tecnologicos",
                "classification_confidence": 0.9,
            }
        ]

    class _EmbeddingsStub:
        async def generar_embedding(self, texto):
            captured["texto"] = texto
            return [0.1, 0.2]

    class _SupabaseQueryStub:
        def __init__(self):
            self.payload = None

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            return SimpleNamespace(data=[self.payload])

    class _SupabaseStub:
        def table(self, _table_name):
            return _SupabaseQueryStub()

    monkeypatch.setattr(
        "services.onboarding.registration.registro_proveedor.run_supabase",
        _fake_run_supabase,
    )
    monkeypatch.setattr(
        "services.onboarding.registration.registro_proveedor.clasificar_servicios_livianos",
        _fake_clasificar_servicios_livianos,
    )
    monkeypatch.setattr(
        "services.onboarding.registration.registro_proveedor.construir_texto_embedding_canonico",
        lambda **_kwargs: "canon-text",
    )

    from services.onboarding.registration.registro_proveedor import (
        insertar_servicios_proveedor,
    )

    resultado = await insertar_servicios_proveedor(
        supabase=_SupabaseStub(),
        proveedor_id="prov-1",
        servicios=[{"service_name": "Desarrollo de software", "raw_service_text": "dev"}],
        servicio_embeddings=_EmbeddingsStub(),
    )

    assert resultado["inserted_count"] == 1
    assert captured["texto"] == "canon-text"

def test_actualizar_servicios_persiste_servicio_sin_canonizacion_taxonomica(
    monkeypatch,
):
    import importlib

    modulo_actualizar_servicios = importlib.import_module(
        "services.maintenance.actualizar_servicios"
    )
    actualizar_servicios = modulo_actualizar_servicios.actualizar_servicios

    class _SupabaseQueryStub:
        def __init__(self, table_name, tables):
            self.table_name = table_name
            self.tables = tables
            self._single = False

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

        def single(self):
            self._single = True
            return self

        def execute(self):
            datos = self.tables.get(self.table_name, [])
            if self._single:
                if isinstance(datos, list):
                    datos = datos[0] if datos else None
                self._single = False
            return SimpleNamespace(data=datos)

    class _SupabaseStub:
        def __init__(self, tables):
            self.tables = tables

        def table(self, table_name: str):
            return _SupabaseQueryStub(table_name, self.tables)

    supabase = _SupabaseStub(
        {
            "service_taxonomy_publications": [{"version": 1, "status": "published"}],
            "service_domains": [
                {"id": "dom-1", "code": "legal", "status": "published"}
            ],
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
        "services.onboarding.registration.insertar_servicios_proveedor",
        _fake_insertar_servicios_proveedor,
    )

    principal_stub = types.ModuleType("principal")
    principal_stub.supabase = supabase
    principal_stub.servicio_embeddings = object()
    sys.modules["principal"] = principal_stub
    flows_sesion_stub = types.ModuleType("flows.session")

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
    sys.modules["flows.session"] = flows_sesion_stub

    resultado = asyncio.run(actualizar_servicios("prov-1", ["laboralista"]))

    assert resultado == ["laboralista"]
