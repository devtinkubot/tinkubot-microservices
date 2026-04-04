"""Tests para la compuerta de necesidad/problema en awaiting_service."""

import pytest
from flows.manejadores_estados.manejo_servicio import (
    procesar_estado_esperando_servicio,
)
from templates.mensajes.validacion import (
    mensaje_aclarar_detalle_servicio,
    mensaje_solicitar_precision_servicio,
    mensaje_solicitar_detalle_servicio,
)


@pytest.mark.asyncio
async def test_rechazo_semantico_con_extraccion_pide_detalle_y_guarda_hint():
    flujo = {"state": "awaiting_service"}
    prompt = "¿Qué necesitas resolver?"

    async def extraer_fn(_texto: str):
        return "plomero"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="plomero",
        saludos=set(),
        prompt_inicial=prompt,
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert flujo_actualizado["service_candidate_hint"] == "plomero"
    assert flujo_actualizado["service_candidate_hint_label"] == "plomero"
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("plomero")
    assert "ui" not in respuesta


@pytest.mark.asyncio
async def test_acepta_necesidad_concreta_y_pasa_a_confirmacion():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "reparación de lavadoras",
            "domain": "servicios del hogar",
            "category": "electrodomésticos",
        }

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="mi lavadora no enciende",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "reparación de lavadoras"
    assert flujo_actualizado["service_domain"] == "servicios del hogar"
    assert flujo_actualizado["service_category"] == "electrodomésticos"
    assert flujo_actualizado["descripcion_problema"] == "mi lavadora no enciende"
    assert "Servicio normalizado: reparación de lavadoras" in flujo_actualizado[
        "service_full"
    ]
    assert "Dominio: servicios del hogar" in flujo_actualizado["service_full"]
    assert "Categoría: electrodomésticos" in flujo_actualizado["service_full"]
    assert "¿Es este el servicio que buscas:" in respuesta["response"]
    assert respuesta["ui"]["type"] == "buttons"


@pytest.mark.asyncio
async def test_jardineria_mixta_confirma_servicio_normalizado():
    flujo = {
        "state": "awaiting_service",
        "city": "Cuenca",
        "city_confirmed": True,
    }

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "mantenimiento de jardines",
            "domain": "jardinería",
            "category": "mantenimiento de jardines",
            "search_profile": {
                "raw_input": "El jardín de la casa está sucio y los árboles frutales necesitan poda, necesito que alguien me ayude.",
                "primary_service": "mantenimiento de jardines",
                "domain": "jardinería",
                "category": "mantenimiento de jardines",
                "signals": [
                    "servicio objetivo: mantenimiento de jardines",
                    "dominio: jardinería",
                    "categoría: mantenimiento de jardines",
                ],
                "confidence": 0.92,
                "source": "client",
            },
        }

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto=(
            "El jardín de la casa está sucio y los árboles frutales necesitan poda, "
            "necesito que alguien me ayude."
        ),
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "mantenimiento de jardines"
    assert flujo_actualizado["service_domain"] == "jardinería"
    assert flujo_actualizado["service_category"] == "mantenimiento de jardines"
    assert flujo_actualizado["search_profile"]["primary_service"] == "mantenimiento de jardines"
    assert "¿Es este el servicio que buscas: *mantenimiento de jardines*?" in respuesta[
        "response"
    ]
    assert respuesta["ui"]["type"] == "buttons"


@pytest.mark.asyncio
async def test_servicio_sin_taxonomia_pide_precision_y_no_confirma():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "mantenimiento de jardines",
            "domain": None,
            "category": None,
            "search_profile": {
                "raw_input": "Servicios de jardinería y poda de árboles",
                "primary_service": "mantenimiento de jardines",
                "domain": None,
                "category": None,
                "signals": ["servicio objetivo: mantenimiento de jardines"],
                "confidence": 0.4,
                "source": "client",
            },
        }

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="Servicios de jardinería y poda de árboles",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert flujo_actualizado["service_candidate_hint"] == "mantenimiento de jardines"
    assert "service_candidate" not in flujo_actualizado
    assert respuesta["response"] == mensaje_solicitar_precision_servicio(
        "mantenimiento de jardines"
    )


@pytest.mark.asyncio
async def test_gate_v2_rechaza_pero_extrae_y_pide_detalle():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "servicio de capitán de embarcación"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="capitan de barco",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert (
        flujo_actualizado["service_candidate_hint"]
        == "servicio de capitán de embarcación"
    )
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("capitan de barco")
    assert "ui" not in respuesta
    assert flujo_actualizado["service_candidate_hint_label"] == "capitan de barco"


@pytest.mark.asyncio
async def test_gate_v2_rechaza_y_sin_extraccion_bloquea():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return None

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="capitan de barco",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("capitan de barco")
    assert flujo_actualizado["state"] == "awaiting_service"
    assert "service_candidate" not in flujo_actualizado


@pytest.mark.asyncio
async def test_entrada_generica_usa_hint_limpio_y_no_repite_texto_crudo():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "carpintero"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="necesito un carpintero",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["service_candidate_hint"] == "carpintero"
    assert flujo_actualizado["service_candidate_hint_label"] == "carpintero"
    assert respuesta["response"] == mensaje_solicitar_detalle_servicio("carpintero")


@pytest.mark.asyncio
async def test_asesor_contable_pasa_a_confirmacion_sin_bloqueo_local():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "asesoría contable",
            "domain": "servicios legales y contables",
            "category": "contabilidad",
        }

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="necesito un asesor contable",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "asesoría contable"
    assert flujo_actualizado["service_domain"] == "servicios legales y contables"
    assert flujo_actualizado["service_category"] == "contabilidad"
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_hint_previsto_se_combina_con_detalle_para_extraer_servicio():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "carpintero",
        "service_candidate_hint_label": "carpintero",
    }
    prompt = "¿Qué necesitas resolver?"
    llamadas = []

    async def extraer_fn(texto: str):
        llamadas.append(texto)
        return {
            "normalized_service": "fabricación de clóset a medida",
            "domain": "construccion_hogar",
            "category": "carpintería",
            "search_profile": {
                "raw_input": texto,
                "primary_service": "fabricación de clóset a medida",
                "domain": "construccion_hogar",
                "category": "carpintería",
                "signals": [
                    "servicio objetivo: fabricación de clóset a medida",
                    "dominio: construccion_hogar",
                    "categoría: carpintería",
                ],
                "confidence": 0.91,
                "source": "client",
            },
        }

    async def validar_necesidad_fn(_texto: str):
        return True

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="quiero hacer un clóset a medida para mi cuarto",
        saludos=set(),
        prompt_inicial=prompt,
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "fabricación de clóset a medida"
    assert "Servicio de referencia: carpintero." in llamadas[0]
    assert (
        "Servicio de referencia: carpintero."
        in flujo_actualizado["service_full"]
    )
    assert "Servicio normalizado: fabricación de clóset a medida" in flujo_actualizado[
        "service_full"
    ]
    assert "Necesidad del usuario: quiero hacer un clóset a medida para mi cuarto" in flujo_actualizado[
        "service_full"
    ]
    assert (
        flujo_actualizado["descripcion_problema"]
        == "quiero hacer un clóset a medida para mi cuarto"
    )
    assert "service_candidate_hint" not in flujo_actualizado
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_servicio_generico_critico_pide_precision_y_no_busca():
    flujo = {"state": "awaiting_service"}
    eventos = []

    async def extraer_fn(_texto: str):
        return "transporte de mercancías"

    async def validar_necesidad_fn(_texto: str):
        return True

    async def detectar_dominio_generico_fn(servicio: str):
        if servicio == "transporte de mercancías":
            return "transporte"
        return None

    async def registrar_evento_fn(**payload):
        eventos.append(payload)

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="necesito llevar mercaderia",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
        detectar_dominio_generico_fn=detectar_dominio_generico_fn,
        registrar_evento_fn=registrar_evento_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert flujo_actualizado["service_candidate_hint"] == "transporte de mercancías"
    assert "service_candidate" not in flujo_actualizado
    assert respuesta["response"] == mensaje_solicitar_precision_servicio(
        "transporte de mercancías"
    )
    assert [evento["event_name"] for evento in eventos] == [
        "generic_service_blocked",
        "precision_prompt_fallback_used",
        "clarification_requested",
    ]


@pytest.mark.asyncio
async def test_taxonomia_publicada_puede_bloquear_servicio_generico_fuera_del_hardcode():
    flujo = {"state": "awaiting_service"}

    async def extraer_fn(_texto: str):
        return "servicio inmobiliario"

    async def validar_necesidad_fn(_texto: str):
        return True

    async def detectar_dominio_generico_fn(servicio: str):
        if servicio == "servicio inmobiliario":
            return "inmobiliario"
        return None

    async def construir_mensaje_precision_fn(servicio: str):
        assert servicio == "servicio inmobiliario"
        return "Indica si buscas comprar, vender o rentar y qué tipo de inmueble."

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="quiero tramitar un servicio inmobiliario",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
        detectar_dominio_generico_fn=detectar_dominio_generico_fn,
        construir_mensaje_precision_fn=construir_mensaje_precision_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert flujo_actualizado["service_candidate_hint"] == "servicio inmobiliario"
    assert "service_candidate" not in flujo_actualizado
    assert (
        respuesta["response"]
        == "Indica si buscas comprar, vender o rentar y qué tipo de inmueble."
    )


@pytest.mark.asyncio
async def test_hint_existente_y_servicio_especifico_pasa_a_confirmacion_aun_si_gate_falla():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "ingeniero sistemas",
        "service_candidate_hint_label": "ingeniero sistemas",
    }

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "desarrollo de aplicaciones móviles",
            "domain": "tecnologia",
            "category": "desarrollo de software",
        }

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="Para qué desarrolle la app movil que requerimos",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "desarrollo de aplicaciones móviles"
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_hint_existente_y_frase_corta_concreta_pasa_a_confirmacion():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "mecanico",
        "service_candidate_hint_label": "mecanico",
    }

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "cambio de aceite de motor",
            "domain": "automotriz",
            "category": "mecánica preventiva",
        }

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="Cambio de aceite",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert flujo_actualizado["service_candidate"] == "cambio de aceite de motor"
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_hint_existente_y_planos_para_casa_pasa_a_confirmacion():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "arquitecto",
        "service_candidate_hint_label": "arquitecto",
    }

    async def extraer_fn(_texto: str):
        return {
            "normalized_service": "diseño de planos arquitectónicos",
            "domain": "construccion_hogar",
            "category": "arquitectura",
        }

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="Planos para una casa",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "confirm_service"
    assert (
        flujo_actualizado["service_candidate"] == "diseño de planos arquitectónicos"
    )
    assert "¿Es este el servicio que buscas:" in respuesta["response"]


@pytest.mark.asyncio
async def test_respuesta_meta_no_reemplaza_hint_y_aclara_que_detalle_falta():
    flujo = {
        "state": "awaiting_service",
        "service_candidate_hint": "desarrollo de aplicaciones móviles",
        "service_candidate_hint_label": "desarrollo de aplicaciones móviles",
    }

    async def extraer_fn(_texto: str):
        return "No entiendo"

    async def validar_necesidad_fn(_texto: str):
        return False

    flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
        flujo=flujo,
        texto="No entiendo",
        saludos=set(),
        prompt_inicial="¿Qué necesitas resolver?",
        extraer_fn=extraer_fn,
        validar_necesidad_fn=validar_necesidad_fn,
    )

    assert flujo_actualizado["state"] == "awaiting_service"
    assert (
        flujo_actualizado["service_candidate_hint"]
        == "desarrollo de aplicaciones móviles"
    )
    assert respuesta["response"] == mensaje_aclarar_detalle_servicio(
        "desarrollo de aplicaciones móviles"
    )
