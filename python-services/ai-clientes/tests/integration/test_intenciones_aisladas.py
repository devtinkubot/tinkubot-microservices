"""Prueba de regresión de conversación aislada para intenciones de cliente."""

import logging

import pytest

from flows import enrutador as enrutador_module
from flows.enrutador import enrutar_estado


class _RepoFlujoStub:
    def __init__(self):
        self.last_saved = None

    async def guardar(self, telefono: str, datos: dict):
        self.last_saved = (telefono, dict(datos))


class _GestorSesionesStub:
    async def guardar_sesion(self, telefono: str, texto: str, es_bot: bool):
        return None


class _ExtractorIAStub:
    def __init__(self, perfil_por_texto: dict[str, dict]):
        self.perfil_por_texto = perfil_por_texto

    async def es_necesidad_o_problema(self, texto: str) -> bool:
        return True

    async def extraer_servicio_con_ia(self, texto: str):
        for clave, perfil in self.perfil_por_texto.items():
            if clave in texto.lower():
                return dict(perfil)
        return {
            "normalized_service": "servicio desconocido",
            "domain": "otros",
            "category": "otros",
            "domain_code": "otros",
            "category_name": "otros",
        }

    async def extraer_ubicacion_con_ia(self, _texto: str) -> str:
        return ""


class _OrquestadorStub:
    def __init__(self, perfil_por_texto: dict[str, dict]):
        self.repositorio_flujo = _RepoFlujoStub()
        self.gestor_sesiones = _GestorSesionesStub()
        self.extractor_ia = _ExtractorIAStub(perfil_por_texto)
        self.repositorio_clientes = self
        self.greetings = {"hola", "buenas"}
        self.logger = logging.getLogger("test-intenciones-aisladas")
        self.farewell_message = "Hasta luego"
        self.max_confirm_attempts = 3
        self.confirm_calls = []
        self.reset_calls = 0

    async def guardar_flujo(self, telefono: str, datos: dict):
        self.repositorio_flujo.last_saved = (telefono, dict(datos))

    async def resetear_flujo(self, telefono: str):
        self.reset_calls += 1
        return None

    async def obtener_o_crear(self, telefono: str):
        return {
            "id": f"c-{telefono}",
            "city": "Cuenca",
            "city_confirmed_at": "2026-01-01T00:00:00",
        }

    async def obtener_o_crear_cliente(self, telefono: str):
        return await self.obtener_o_crear(telefono)

    async def enviar_texto_whatsapp(
        self, telefono: str, mensaje: str, metadata: dict | None = None
    ):
        _ = metadata
        return True

    async def construir_prompt_inicial_servicio(self):
        return {
            "response": "*¿Qué necesitas resolver?*.",
            "ui": {
                "type": "list",
                "options": [
                    {"id": "popular_service::plomero", "title": "Plomero"},
                ],
            },
        }

    async def _procesar_awaiting_service(
        self, _telefono, flujo, texto, _responder, _cliente_id
    ):
        from flows.manejadores_estados.manejo_servicio import (
            procesar_estado_esperando_servicio,
        )

        return (
            await procesar_estado_esperando_servicio(
                flujo=flujo,
                texto=texto,
                saludos=self.greetings,
                prompt_inicial="*¿Qué necesitas resolver?*.",
                extraer_fn=self.extractor_ia.extraer_servicio_con_ia,
                validar_necesidad_fn=self.extractor_ia.es_necesidad_o_problema,
            )
        )[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("texto", "service", "domain", "category"),
    [
        (
            "necesito un asesor contable",
            "asesoría contable",
            "finanzas",
            "contabilidad",
        ),
        (
            "requiere un administrador de proyectos de tics",
            "gestión de proyectos de tics",
            "tecnología",
            "gestión de proyectos de ti",
        ),
        (
            "la aplicacion movil de mi trabajo esta con fallas y necesito alguien que lo arregle",
            "arreglar aplicación móvil",
            "tecnología",
            "desarrollo de software",
        ),
    ],
)
async def test_intenciones_aisladas_confirman_y_disparan_busqueda(
    monkeypatch, texto, service, domain, category
):
    orquestador = _OrquestadorStub(
        perfil_por_texto={
            "asesor contable": {
                "normalized_service": "asesoría contable",
                "domain": "finanzas",
                "category": "contabilidad",
                "domain_code": "finanzas",
                "category_name": "contabilidad",
            },
            "administrador de proyectos de tics": {
                "normalized_service": "gestión de proyectos de tics",
                "domain": "tecnología",
                "category": "gestión de proyectos de ti",
                "domain_code": "tecnologia",
                "category_name": "gestion de proyectos de ti",
            },
            "aplicacion movil": {
                "normalized_service": "arreglar aplicación móvil",
                "domain": "tecnología",
                "category": "desarrollo de software",
                "domain_code": "tecnologia",
                "category_name": "desarrollo de software",
            },
        }
    )

    async def fake_transicionar_a_busqueda_desde_servicio(
        telefono,
        flujo,
        perfil_cliente,
        enviar_mensaje_callback,
        guardar_flujo_callback,
        buscar_proveedores_fn=None,
    ):
        _ = buscar_proveedores_fn
        orquestador.confirm_calls.append(
            {
                "telefono": telefono,
                "service": flujo.get("service"),
                "city": flujo.get("city"),
                "perfil_cliente": perfil_cliente,
            }
        )
        return {
            "response": "⏳ *Busco expertos.* Te aviso en breve.",
            "messages": [{"response": "⏳ *Busco expertos.* Te aviso en breve."}],
        }

    monkeypatch.setattr(
        enrutador_module,
        "transicionar_a_busqueda_desde_servicio",
        fake_transicionar_a_busqueda_desde_servicio,
    )

    telefono = "+593959091325"
    flujo = {"state": "awaiting_service", "city": "Cuenca", "city_confirmed": True}

    primera = await enrutar_estado(
        orquestador,
        telefono=telefono,
        flujo=flujo,
        texto=texto,
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={"city": "Cuenca"},
        cliente_id="cust-1",
    )

    assert flujo["state"] == "confirm_service"
    assert flujo["service_candidate"] == service
    assert flujo["service_domain"] == domain
    assert flujo["service_category"] == category
    assert "¿Es este el servicio que buscas:" in primera["response"]

    segunda = await enrutar_estado(
        orquestador,
        telefono=telefono,
        flujo=flujo,
        texto="sí",
        seleccionado=None,
        tipo_mensaje="text",
        ubicacion={"city": "Cuenca"},
        cliente_id="cust-1",
    )

    assert segunda["response"] == "⏳ *Busco expertos.* Te aviso en breve."
    assert orquestador.confirm_calls[-1]["service"] == service
    assert orquestador.confirm_calls[-1]["city"] == "Cuenca"
    assert orquestador.reset_calls == 0
