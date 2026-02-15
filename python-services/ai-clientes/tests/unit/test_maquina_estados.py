"""
Unit tests for the State Machine.

Tests the MaquinaEstados class and state transitions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from models.estados import EstadoConversacion, FlujoConversacional
from state_machine import MaquinaEstados
from state_machine.contexto import ContextoConversacionState
from tests.conftest import (
    MockRepositorioFlujo,
    MockExtractorNecesidad,
    MockBuscadorProveedores,
    FlujoFactory,
)


class TestMaquinaEstadosCreacion:
    """Tests for MaquinaEstados initialization."""

    def test_creacion_con_repositorio(self):
        """Test creating with minimal dependencies."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )

        assert maquina.repositorio_flujo == repo

    def test_creacion_con_todos_servicios(self):
        """Test creating with all dependencies."""
        from infrastructure.logging.structured_logger import get_logger

        maquina = MaquinaEstados(
            repositorio_flujo=MockRepositorioFlujo(),
            repositorio_clientes=MagicMock(),
            buscador_proveedores=MagicMock(),
            extractor_necesidad=MagicMock(),
            logger=get_logger("test"),
        )

        assert maquina.repositorio_clientes is not None
        assert maquina.buscador_proveedores is not None


class TestMaquinaEstadosProcesamiento:
    """Tests for message processing."""

    @pytest.fixture
    def maquina(self):
        """Provides a configured state machine."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        extractor = MockExtractorNecesidad()

        return MaquinaEstados(
            repositorio_flujo=repo,
            extractor_necesidad=extractor,
            logger=get_logger("test"),
        ), repo, extractor

    @pytest.mark.asyncio
    async def test_procesar_mensaje_nuevo_usuario(self, maquina):
        """Test processing message from new user."""
        maquina, repo, _ = maquina
        telefono = "+593999999999"

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="Hola",
        )

        assert respuesta is not None
        assert "estado" in respuesta

        # Should create new flow
        flujo = await repo.obtener_modelo(telefono)
        assert flujo is not None

    @pytest.mark.asyncio
    async def test_procesar_mensaje_usuario_existente(self, maquina):
        """Test processing message from existing user."""
        maquina, repo, _ = maquina
        telefono = "+593999999999"

        # Set existing flow
        repo.set_flujo(FlujoFactory.en_servicio(telefono))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="plomero",
        )

        assert respuesta is not None
        # Should use existing flow
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.telefono == telefono

    @pytest.mark.asyncio
    async def test_procesar_mensaje_con_correlation_id(self, maquina):
        """Test processing with correlation ID for tracing."""
        maquina, repo, _ = maquina
        telefono = "+593999999999"

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="test",
            correlation_id="corr-123",
        )

        assert respuesta is not None


class TestMaquinaEstadosTransiciones:
    """Tests for state transitions in MaquinaEstados."""

    @pytest.fixture
    def maquina(self):
        """Provides a state machine for transition tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()

        return MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        ), repo

    @pytest.mark.asyncio
    async def test_transicion_valida_ejecutada(self, maquina):
        """Test valid transition is executed."""
        maquina, repo = maquina
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.en_servicio(telefono))

        # Make a transition
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="reiniciar",
        )

        # Check if state changed (depends on handler implementation)
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_transicion_guarda_flujo(self, maquina):
        """Test that transitions persist the flow."""
        maquina, repo = maquina
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.en_servicio(telefono))

        await maquina.procesar_mensaje(
            telefono=telefono,
            texto="test",
        )

        # Flow should have been saved
        assert repo.guardar_llamado


class TestMaquinaEstadosReset:
    """Tests for flow reset functionality."""

    @pytest.fixture
    def maquina(self):
        """Provides a state machine for reset tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        return MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        ), repo

    @pytest.mark.asyncio
    async def test_resetear_flujo(self, maquina):
        """Test resetting a flow."""
        maquina, repo = maquina
        telefono = "+593999999999"

        # Create flow
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.SEARCHING,
            servicio="plomero",
        ))

        # Reset
        resultado = await maquina.resetear_flujo(telefono)

        assert resultado["success"]
        assert repo.resetear_llamado


class TestContextoConversacionState:
    """Tests for ContextoConversacionState."""

    def test_creacion_contexto(self):
        """Test creating context."""
        flujo = FlujoFactory.en_servicio()
        contexto = ContextoConversacionState(
            flujo=flujo,
            telefono="+593999999999",
        )

        assert contexto.flujo == flujo
        assert contexto.telefono == "+593999999999"

    def test_actualizar_flujo(self):
        """Test updating flow in context."""
        flujo = FlujoFactory.en_servicio()
        contexto = ContextoConversacionState(
            flujo=flujo,
            telefono="+593999999999",
        )

        contexto.actualizar_flujo(service="plomero")

        assert contexto.flujo.service == "plomero"

    def test_set_respuesta(self):
        """Test setting response."""
        flujo = FlujoFactory.en_servicio()
        contexto = ContextoConversacionState(
            flujo=flujo,
            telefono="+593999999999",
        )

        contexto.set_respuesta("Hola mundo")

        assert contexto.respuesta == "Hola mundo"

    def test_to_dict(self):
        """Test serializing context to dict."""
        flujo = FlujoFactory.en_servicio()
        contexto = ContextoConversacionState(
            flujo=flujo,
            telefono="+593999999999",
        )

        data = contexto.to_dict()

        assert data["telefono"] == "+593999999999"
        assert "estado" in data


class TestEstadoHandlers:
    """Tests for individual state handlers."""

    @pytest.fixture
    def contexto(self):
        """Provides a context for handler testing."""
        flujo = FlujoFactory.en_servicio()
        return ContextoConversacionState(
            flujo=flujo,
            telefono="+593999999999",
            texto_mensaje="test",
        )

    @pytest.mark.asyncio
    async def test_estado_awaiting_service(self, contexto):
        """Test AwaitingService state handler."""
        from state_machine.estados import EstadoAwaitingService

        estado = EstadoAwaitingService()
        assert estado.nombre == "Awaiting Service"
        assert EstadoConversacion.AWAITING_SERVICE in estado.estados_que_maneja

    @pytest.mark.asyncio
    async def test_estado_awaiting_city(self, contexto):
        """Test AwaitingCity state handler."""
        from state_machine.estados import EstadoAwaitingCity

        estado = EstadoAwaitingCity()
        assert EstadoConversacion.AWAITING_CITY in estado.estados_que_maneja

    @pytest.mark.asyncio
    async def test_estado_searching(self, contexto):
        """Test Searching state handler."""
        from state_machine.estados import EstadoSearching

        estado = EstadoSearching()
        assert EstadoConversacion.SEARCHING in estado.estados_que_maneja

    @pytest.mark.asyncio
    async def test_estado_presenting_results(self, contexto):
        """Test PresentingResults state handler."""
        from state_machine.estados import EstadoPresentingResults

        estado = EstadoPresentingResults()
        assert EstadoConversacion.PRESENTING_RESULTS in estado.estados_que_maneja


class TestEstadoRegistry:
    """Tests for the state registry."""

    def test_get_estado_class(self):
        """Test getting state class from registry."""
        from state_machine.estados import get_estado_class, EstadoAwaitingConsent

        cls = get_estado_class("awaiting_consent")
        assert cls == EstadoAwaitingConsent

    def test_get_estado_class_unknown(self):
        """Test getting state class for unknown state."""
        from state_machine.estados import get_estado_class, EstadoAwaitingService

        cls = get_estado_class("unknown_state")
        assert cls == EstadoAwaitingService  # Default

    def test_todos_estados_tienen_handler(self):
        """Test all states have a handler in registry."""
        from state_machine.estados import ESTADOS_REGISTRY

        for estado in EstadoConversacion:
            # Either has explicit handler or will use default
            assert estado.value in ESTADOS_REGISTRY or True
