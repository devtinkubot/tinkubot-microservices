import sys
import types
from pathlib import Path

import pytest

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.onboarding.router as modulo_onboarding_router  # noqa: E402
import routes.onboarding.router as modulo_routes_onboarding  # noqa: E402
from flows.onboarding.handlers.ciudad import (  # noqa: E402
    manejar_espera_ciudad_onboarding,
)
from flows.onboarding.handlers.documentos import (  # noqa: E402
    manejar_dni_frontal_onboarding,
    manejar_foto_perfil_onboarding,
)
from flows.onboarding.handlers.real_phone import (  # noqa: E402
    manejar_espera_real_phone_onboarding,
)
from flows.onboarding.router import manejar_estado_onboarding  # noqa: E402
from templates.onboarding.telefono import preguntar_real_phone  # noqa: E402


@pytest.mark.asyncio
async def test_ciudad_onboarding_avanza_a_documentos(monkeypatch):
    async def _fake_resolver_ciudad_desde_texto(texto):
        assert texto == "Cuenca"
        return "Cuenca"

    monkeypatch.setattr(
        "flows.onboarding.handlers.ciudad._resolver_ciudad_desde_texto",
        _fake_resolver_ciudad_desde_texto,
    )

    flujo = {"state": "onboarding_city"}
    respuesta = await manejar_espera_ciudad_onboarding(
        flujo=flujo,
        texto_mensaje="Cuenca",
        carga={},
    )

    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "onboarding_dni_front_photo"
    assert respuesta["messages"][0]["response"].startswith(
        "*Envía una foto frontal de tu cédula.*"
    )


@pytest.mark.asyncio
async def test_dni_frontal_onboarding_avanza_a_selfie():
    flujo = {"state": "onboarding_dni_front_photo", "provider_id": "prov-1"}
    respuesta = await manejar_dni_frontal_onboarding(
        flujo=flujo,
        carga={"image_base64": "front-image"},
        telefono="593999111299@s.whatsapp.net",
    )

    assert flujo["dni_front_image"] == "front-image"
    assert flujo["phone"] == "593999111299@s.whatsapp.net"
    assert flujo["state"] == "onboarding_face_photo"
    assert respuesta["messages"][0]["response"].startswith("*Envía tu foto de perfil.*")


@pytest.mark.asyncio
async def test_foto_perfil_onboarding_avanza_a_experiencia():
    flujo = {"state": "onboarding_face_photo", "provider_id": "prov-1"}
    respuesta = await manejar_foto_perfil_onboarding(
        flujo=flujo,
        carga={"image_base64": "face-image"},
        telefono="593999111299@s.whatsapp.net",
    )

    assert flujo["face_image"] == "face-image"
    assert flujo["phone"] == "593999111299@s.whatsapp.net"
    assert flujo["state"] == "onboarding_experience"
    assert respuesta["messages"][0]["response"] == "Selecciona tus *años de experiencia*."


@pytest.mark.asyncio
async def test_real_phone_onboarding_avanza_a_ciudad():
    flujo = {"state": "onboarding_real_phone"}
    respuesta = await manejar_espera_real_phone_onboarding(
        flujo=flujo,
        texto_mensaje="+593 99 111 2222",
    )

    assert flujo["state"] == "onboarding_city"
    assert flujo["real_phone"] == "593991112222"
    assert respuesta["messages"][0]["response"].startswith(
        "Ahora comparte tu *ubicación*"
    )


def test_prompt_real_phone_onboarding_existe():
    assert "comparte tu número real" in preguntar_real_phone().lower()


@pytest.mark.asyncio
async def test_router_onboarding_nuevo_enruta_ciudad_y_documentos(monkeypatch):
    async def _fake_ciudad(**_kwargs):
        return {"success": True, "messages": [{"response": "ok ciudad"}]}

    async def _fake_dni(**_kwargs):
        return {"success": True, "messages": [{"response": "ok dni"}]}

    async def _fake_real_phone(**_kwargs):
        return {"success": True, "messages": [{"response": "ok phone"}]}

    monkeypatch.setattr(
        modulo_onboarding_router,
        "manejar_espera_ciudad_onboarding",
        _fake_ciudad,
    )
    monkeypatch.setattr(
        modulo_onboarding_router,
        "manejar_dni_frontal_onboarding",
        _fake_dni,
    )
    monkeypatch.setattr(
        modulo_onboarding_router,
        "manejar_espera_real_phone_onboarding",
        _fake_real_phone,
    )

    respuesta_ciudad = await manejar_estado_onboarding(
        estado="onboarding_city",
        flujo={"mode": "registration"},
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="Cuenca",
        carga={},
        supabase=None,
    )
    respuesta_dni = await manejar_estado_onboarding(
        estado="onboarding_dni_front_photo",
        flujo={"mode": "registration"},
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="",
        carga={},
        supabase=None,
    )
    respuesta_phone = await manejar_estado_onboarding(
        estado="onboarding_real_phone",
        flujo={"mode": "registration"},
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="+593991112222",
        carga={},
        supabase=None,
    )

    assert respuesta_ciudad["messages"][0]["response"] == "ok ciudad"
    assert respuesta_dni["messages"][0]["response"] == "ok dni"
    assert respuesta_phone["messages"][0]["response"] == "ok phone"


@pytest.mark.asyncio
async def test_router_onboarding_add_another_service_enruta_decision(monkeypatch):
    async def _fake_decision(*, flujo, texto_mensaje, selected_option=None):
        assert flujo["state"] == "onboarding_add_another_service"
        assert texto_mensaje == "sí"
        assert selected_option == "onboarding_add_another_service_yes"
        flujo["state"] = "onboarding_specialty"
        return {"success": True, "messages": [{"response": "ok add another"}]}

    monkeypatch.setattr(
        modulo_onboarding_router,
        "manejar_decision_agregar_otro_servicio_onboarding",
        _fake_decision,
    )

    flujo = {"state": "onboarding_add_another_service"}
    respuesta = await manejar_estado_onboarding(
        estado="onboarding_add_another_service",
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="sí",
        carga={"selected_option": "onboarding_add_another_service_yes"},
        supabase=None,
    )

    assert flujo["state"] == "onboarding_specialty"
    assert respuesta["messages"][0]["response"] == "ok add another"


@pytest.mark.asyncio
async def test_boundary_onboarding_sin_consentimiento_pide_consentimiento():
    flujo = {}

    respuesta = await modulo_routes_onboarding.manejar_contexto_onboarding(
        estado=None,
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="hola",
        carga={},
        perfil_proveedor=None,
        supabase=None,
        servicio_embeddings=None,
        cliente_openai=None,
        subir_medios_identidad=None,
        opcion_menu=None,
        tiene_consentimiento=False,
        esta_registrado=False,
        logger=None,
    )

    assert respuesta is not None
    assert flujo["state"] == "onboarding_consent"
    assert respuesta["response"]["messages"][0]["response"].startswith(
        "Para poder conectarte con clientes"
    )


@pytest.mark.asyncio
async def test_boundary_onboarding_no_reclama_registrado_sin_consentimiento():
    flujo = {"state": "onboarding_city", "has_consent": False, "provider_id": "prov-1"}

    respuesta = await modulo_routes_onboarding.manejar_contexto_onboarding(
        estado="onboarding_city",
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="hola",
        carga={},
        perfil_proveedor={"id": "prov-1", "has_consent": True},
        supabase=None,
        servicio_embeddings=None,
        cliente_openai=None,
        subir_medios_identidad=None,
        opcion_menu=None,
        tiene_consentimiento=False,
        esta_registrado=True,
        logger=None,
    )

    assert respuesta is None
    assert flujo["provider_id"] == "prov-1"
    assert flujo["has_consent"] is False


@pytest.mark.asyncio
async def test_boundary_onboarding_no_reclama_menu_principal():
    flujo = {"state": "awaiting_menu_option", "has_consent": False}

    respuesta = await modulo_routes_onboarding.manejar_contexto_onboarding(
        estado="awaiting_menu_option",
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="hola",
        carga={},
        perfil_proveedor=None,
        supabase=None,
        servicio_embeddings=None,
        cliente_openai=None,
        subir_medios_identidad=None,
        opcion_menu=None,
        tiene_consentimiento=True,
        esta_registrado=False,
        logger=None,
    )

    assert respuesta is None
    assert flujo["state"] == "awaiting_menu_option"


@pytest.mark.asyncio
async def test_boundary_onboarding_consentimiento_se_procesa_antes_del_guard(
    monkeypatch,
):
    flujo = {"state": "onboarding_consent", "has_consent": False}
    captured = {}

    async def _fake_estado_onboarding(**kwargs):
        captured["estado"] = kwargs["estado"]
        return {"success": True, "messages": [{"response": "ok consent"}]}

    monkeypatch.setattr(
        modulo_routes_onboarding,
        "manejar_estado_onboarding",
        _fake_estado_onboarding,
    )

    respuesta = await modulo_routes_onboarding.manejar_contexto_onboarding(
        estado="onboarding_consent",
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="continue_provider_onboarding",
        carga={"selected_option": "continue_provider_onboarding"},
        perfil_proveedor=None,
        supabase=None,
        servicio_embeddings=None,
        cliente_openai=None,
        subir_medios_identidad=None,
        opcion_menu=None,
        tiene_consentimiento=False,
        esta_registrado=False,
        logger=None,
    )

    assert captured["estado"] == "onboarding_consent"
    assert respuesta is not None
    assert respuesta["response"]["messages"][0]["response"] == "ok consent"


@pytest.mark.asyncio
async def test_boundary_onboarding_delega_estado_real(monkeypatch):
    flujo = {"state": "onboarding_city", "has_consent": True}

    async def _fake_estado_onboarding(**kwargs):
        assert kwargs["estado"] == "onboarding_city"
        return {"success": True, "messages": [{"response": "ok boundary"}]}

    monkeypatch.setattr(
        modulo_routes_onboarding,
        "manejar_estado_onboarding",
        _fake_estado_onboarding,
    )

    respuesta = await modulo_routes_onboarding.manejar_contexto_onboarding(
        estado="onboarding_city",
        flujo=flujo,
        telefono="593999111299@s.whatsapp.net",
        texto_mensaje="Cuenca",
        carga={},
        perfil_proveedor=None,
        supabase=None,
        servicio_embeddings=None,
        cliente_openai=None,
        subir_medios_identidad=None,
        opcion_menu=None,
        tiene_consentimiento=True,
        esta_registrado=False,
        logger=None,
    )

    assert respuesta is not None
    assert respuesta["response"]["messages"][0]["response"] == "ok boundary"
