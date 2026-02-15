"""
Pruebas de integración para la Máquina de Estados.

Estas pruebas validan que la Máquina de Estados funciona correctamente
cuando USAR_MAQUINA_ESTADOS=true está habilitado.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models.estados import EstadoConversacion, FlujoConversacional
from state_machine import MaquinaEstados
from state_machine.contexto import ContextoConversacionState


class MockRepositorioFlujo:
    """Mock del repositorio de flujos para pruebas."""

    def __init__(self):
        self._flows = {}

    async def obtener_modelo(self, telefono: str):
        return self._flows.get(telefono)

    async def guardar_modelo(self, flujo: FlujoConversacional):
        self._flows[flujo.telefono] = flujo

    async def resetear(self, telefono: str):
        self._flows.pop(telefono, None)

    def set_flujo(self, flujo: FlujoConversacional):
        self._flows[flujo.telefono] = flujo


class MockExtractorNecesidad:
    """Mock del extractor de necesidades IA."""

    async def extraer_servicio_con_ia_pura(self, texto: str, historial: str = ""):
        """Simula extracción de servicio."""
        texto_lower = texto.lower()
        if "plomero" in texto_lower:
            return {"profesion": "plomero", "descripcion": texto}
        if "electricista" in texto_lower:
            return {"profesion": "electricista", "descripcion": texto}
        if "carpintero" in texto_lower:
            return {"profesion": "carpintero", "descripcion": texto}
        return {"profesion": texto[:50], "descripcion": texto}


class MockBuscadorProveedores:
    """Mock del buscador de proveedores."""

    def __init__(self):
        self._proveedores = [
            {
                "id": "prov-1",
                "name": "Juan Pérez",
                "phone_number": "+593999111111",
                "rating": 4.5,
            },
            {
                "id": "prov-2",
                "name": "María García",
                "phone_number": "+593999222222",
                "rating": 4.8,
            },
        ]

    def set_proveedores(self, proveedores):
        self._proveedores = proveedores

    async def buscar(self, servicio: str, ciudad: str, limite: int = 10, **kwargs):
        return {"proveedores": self._proveedores, "total": len(self._proveedores)}


class MockGestorLeads:
    """Mock del gestor de leads."""

    def __init__(self):
        self.leads = []
        self.feedbacks = []

    async def registrar_lead_facturable(self, **kwargs):
        lead_id = f"lead-{len(self.leads) + 1}"
        self.leads.append({"id": lead_id, **kwargs})
        return {"ok": True, "lead_event_id": lead_id}

    async def registrar_feedback_contratacion(self, **kwargs):
        self.feedbacks.append(kwargs)
        return True


class MockServicioConsentimiento:
    """Mock del servicio de consentimiento."""

    def __init__(self):
        self._consents = {}

    async def tiene_consentimiento(self, cliente_id: str) -> bool:
        return self._consents.get(cliente_id, False)

    async def registrar_consentimiento(self, cliente_id: str, aceptado: bool):
        self._consents[cliente_id] = aceptado


@pytest.fixture
def maquina_estados():
    """Proporciona una instancia de MaquinaEstados configurada para pruebas."""
    repo = MockRepositorioFlujo()
    extractor = MockExtractorNecesidad()
    buscador = MockBuscadorProveedores()
    gestor = MockGestorLeads()
    consentimiento = MockServicioConsentimiento()

    from infrastructure.logging.structured_logger import get_logger

    return MaquinaEstados(
        repositorio_flujo=repo,
        buscador_proveedores=buscador,
        extractor_necesidad=extractor,
        gestor_leads=gestor,
        servicio_consentimiento=consentimiento,
        logger=get_logger("test"),
    )


class TestMaquinaEstadosIntegracion:
    """Pruebas de integración de la Máquina de Estados."""

    @pytest.mark.asyncio
    async def test_flujo_completo_busqueda(self, maquina_estados):
        """Prueba el flujo completo: servicio → ciudad → búsqueda → resultados."""
        telefono = "+593999123456"

        # 1. Usuario solicita servicio
        resp1 = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="Necesito un plomero urgente",
        )
        assert resp1["estado"] in ["confirm_service", "awaiting_city", "searching"]

        # 2. Si pide confirmación, confirmar
        if resp1["estado"] == "confirm_service":
            resp1 = await maquina_estados.procesar_mensaje(
                telefono=telefono,
                texto="1",  # Confirmar
            )

        # 3. Si pide ciudad, proporcionar
        if resp1["estado"] == "awaiting_city":
            resp2 = await maquina_estados.procesar_mensaje(
                telefono=telefono,
                texto="Quito",
            )
            assert resp2["estado"] in ["searching", "presenting_results"]

        # Verificar que el flujo avanzó correctamente
        flujo = await maquina_estados.repositorio_flujo.obtener_modelo(telefono)
        assert flujo is not None
        assert flujo.service is not None or flujo.state == EstadoConversacion.SEARCHING

    @pytest.mark.asyncio
    async def test_flujo_con_reinicio(self, maquina_estados):
        """Prueba que el comando de reinicio funciona en cualquier estado."""
        telefono = "+593999999999"

        # Crear un flujo en estado searching
        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.SEARCHING,
            service="plomero",
            city="Quito",
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Enviar comando de reinicio
        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="reiniciar",
        )

        # Verificar que volvió a awaiting_service
        flujo_actualizado = await maquina_estados.repositorio_flujo.obtener_modelo(telefono)
        assert flujo_actualizado.state == EstadoConversacion.AWAITING_SERVICE

    @pytest.mark.asyncio
    async def test_flujo_consentimiento_aceptado(self, maquina_estados):
        """Prueba el flujo de consentimiento cuando el usuario acepta."""
        telefono = "+593999888888"

        # Crear flujo en estado de consentimiento
        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.AWAITING_CONSENT,
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Usuario acepta
        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )

        assert resp["estado"] == EstadoConversacion.AWAITING_SERVICE.value

        # Verificar que el consentimiento quedó registrado
        flujo_actualizado = await maquina_estados.repositorio_flujo.obtener_modelo(telefono)
        assert flujo_actualizado.has_consent is True

    @pytest.mark.asyncio
    async def test_flujo_consentimiento_rechazado(self, maquina_estados):
        """Prueba el flujo de consentimiento cuando el usuario rechaza."""
        telefono = "+593999777777"

        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.AWAITING_CONSENT,
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Usuario rechaza
        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="2",
        )

        assert resp["estado"] == EstadoConversacion.COMPLETED.value

    @pytest.mark.asyncio
    async def test_busqueda_sin_resultados(self, maquina_estados):
        """Prueba el manejo de búsqueda sin resultados."""
        telefono = "+593999666666"

        # Configurar buscador sin resultados
        maquina_estados.buscador_proveedores.set_proveedores([])

        # Crear flujo en estado de búsqueda
        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.SEARCHING,
            service="servicio_raro",
            city="CiudadRemota",
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Ejecutar búsqueda
        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )

        # Debe ofrecer opciones de nueva búsqueda
        assert resp["estado"] == EstadoConversacion.CONFIRM_NEW_SEARCH.value

    @pytest.mark.asyncio
    async def test_compartir_contacto_y_feedback(self, maquina_estados):
        """Prueba el flujo completo de compartir contacto y dar feedback."""
        telefono = "+593999555555"

        proveedor = {
            "id": "prov-test",
            "name": "Test Proveedor",
            "phone_number": "+593999000000",
        }

        # Crear flujo en estado de detalle de proveedor
        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            service="plomero",
            city="Quito",
            providers=[proveedor],
            chosen_provider=proveedor,
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # 1. Usuario quiere contactar
        resp1 = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert resp1["estado"] == EstadoConversacion.AWAITING_CONTACT_SHARE.value

        # 2. Usuario autoriza compartir contacto
        resp2 = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert resp2["estado"] == EstadoConversacion.AWAITING_HIRING_FEEDBACK.value

        # Verificar que se registró el lead
        gestor = maquina_estados.gestor_leads
        assert len(gestor.leads) == 1

        # 3. Usuario da feedback
        resp3 = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="1",  # Excelente
        )
        assert resp3["estado"] == EstadoConversacion.COMPLETED.value

        # Verificar que se guardó el feedback
        assert len(gestor.feedbacks) == 1


class TestMaquinaEstadosEdgeCases:
    """Pruebas de casos límite de la Máquina de Estados."""

    @pytest.mark.asyncio
    async def test_mensaje_vacio(self, maquina_estados):
        """Prueba que un mensaje vacío no rompe el flujo."""
        telefono = "+593999111111"

        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="",
        )

        # No debe haber error
        assert "error" not in resp or resp.get("error") is None

    @pytest.mark.asyncio
    async def test_mensaje_muy_largo(self, maquina_estados):
        """Prueba que un mensaje muy largo se maneja correctamente."""
        telefono = "+593999222222"
        texto_largo = "A" * 5000

        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto=texto_largo,
        )

        # No debe haber error crítico
        assert "response" in resp

    @pytest.mark.asyncio
    async def test_multiples_usuarios_simultaneos(self, maquina_estados):
        """Prueba que múltiples usuarios pueden usar el sistema simultáneamente."""
        usuarios = ["+593999000001", "+593999000002", "+593999000003"]

        # Crear flujos para cada usuario
        for telefono in usuarios:
            flujo = FlujoConversacional(
                telefono=telefono,
                state=EstadoConversacion.AWAITING_SERVICE,
            )
            maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Procesar mensajes de todos los usuarios
        respuestas = []
        for telefono in usuarios:
            resp = await maquina_estados.procesar_mensaje(
                telefono=telefono,
                texto="Necesito un electricista",
            )
            respuestas.append((telefono, resp))

        # Verificar que cada usuario tiene su propio flujo independiente
        for telefono, resp in respuestas:
            flujo = await maquina_estados.repositorio_flujo.obtener_modelo(telefono)
            assert flujo is not None
            assert flujo.telefono == telefono

    @pytest.mark.asyncio
    async def test_estado_corrupto_recuperacion(self, maquina_estados):
        """Prueba que un estado corrupto se recupera correctamente."""
        telefono = "+593999333333"

        # Crear un flujo con estado inválido (simulando corrupción)
        flujo = FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.ERROR,
        )
        maquina_estados.repositorio_flujo.set_flujo(flujo)

        # Usuario envía mensaje
        resp = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto="hola",
        )

        # El sistema debe recuperarse (estado ERROR maneja por EstadoAwaitingService)
        assert resp["estado"] in [
            EstadoConversacion.AWAITING_SERVICE.value,
            EstadoConversacion.ERROR.value,
        ]
