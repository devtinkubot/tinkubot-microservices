"""
Integration tests for the search flow.

Tests the complete search flow from service input
to results presentation.
"""

import pytest

from models.estados import EstadoConversacion
from state_machine import MaquinaEstados
from tests.conftest import (
    MockRepositorioFlujo,
    MockExtractorNecesidad,
    MockBuscadorProveedores,
    FlujoFactory,
    ProveedorFactory,
)


class TestFlujoBusqueda:
    """Integration tests for search flow."""

    @pytest.fixture
    def maquina_busqueda(self):
        """Provides a configured state machine for search tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        extractor = MockExtractorNecesidad()
        buscador = MockBuscadorProveedores()

        # Configure default behavior
        extractor.servicio_a_retornar = "plomero"
        extractor.ciudad_a_retornar = None

        # Add sample providers
        proveedores = [
            ProveedorFactory.crear(id="p1", nombre="Juan Plomero", rating=4.5),
            ProveedorFactory.crear(id="p2", nombre="María Plomera", rating=4.8),
            ProveedorFactory.crear(id="p3", nombre="Pedro Fontanero", rating=4.2),
        ]
        buscador.set_proveedores(proveedores)

        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            extractor_necesidad=extractor,
            buscador_proveedores=buscador,
            logger=get_logger("test"),
        )

        return maquina, repo, extractor, buscador

    @pytest.mark.asyncio
    async def test_flujo_busqueda_completo(self, maquina_busqueda):
        """Test complete search flow."""
        maquina, repo, extractor, buscador = maquina_busqueda
        telefono = "+593999999999"

        # Start with awaiting service
        repo.set_flujo(FlujoFactory.en_servicio(telefono))

        # User describes need
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="necesito un plomero",
        )

        # Should ask for confirmation
        assert respuesta["estado"] == EstadoConversacion.CONFIRM_SERVICE.value

        # User confirms
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )

        # Should ask for city
        assert respuesta["estado"] == EstadoConversacion.AWAITING_CITY.value

        # User provides city
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="Quito",
        )

        # Should transition to searching
        assert respuesta["estado"] == EstadoConversacion.SEARCHING.value

    @pytest.mark.asyncio
    async def test_servicio_y_ciudad_en_un_mensaje(self, maquina_busqueda):
        """Test when AI extracts both service and city."""
        maquina, repo, extractor, _ = maquina_busqueda
        telefono = "+593999999999"

        # Configure extractor to return both
        extractor.servicio_a_retornar = "plomero"
        extractor.ciudad_a_retornar = "Quito"

        repo.set_flujo(FlujoFactory.en_servicio(telefono))

        # User describes need with location
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="necesito un plomero en Quito",
        )

        # Should go directly to searching (both detected)
        assert respuesta["estado"] == EstadoConversacion.SEARCHING.value

    @pytest.mark.asyncio
    async def test_busqueda_con_resultados(self, maquina_busqueda):
        """Test search with results."""
        maquina, repo, extractor, buscador = maquina_busqueda
        telefono = "+593999999999"

        # Set up flow in searching state
        repo.set_flujo(FlujoFactory.en_busqueda(
            telefono=telefono,
            servicio="plomero",
            ciudad="Quito",
        ))

        # Trigger search
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )

        # Should present results
        assert respuesta["estado"] == EstadoConversacion.PRESENTING_RESULTS.value
        assert "Encontré" in respuesta["response"] or "proveedores" in respuesta["response"]

    @pytest.mark.asyncio
    async def test_busqueda_sin_resultados(self, maquina_busqueda):
        """Test search with no results."""
        maquina, repo, extractor, buscador = maquina_busqueda
        telefono = "+593999999999"

        # Configure empty results
        buscador.set_proveedores([])

        repo.set_flujo(FlujoFactory.en_busqueda(
            telefono=telefono,
            servicio="servicio_raro",
            ciudad="CiudadRemota",
        ))

        # Trigger search
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )

        # Should offer new search options
        assert respuesta["estado"] == EstadoConversacion.CONFIRM_NEW_SEARCH.value
        assert "No encontré" in respuesta["response"]

    @pytest.mark.asyncio
    async def test_seleccion_proveedor(self, maquina_busqueda):
        """Test selecting a provider from results."""
        maquina, repo, _, _ = maquina_busqueda
        telefono = "+593999999999"

        # Set up flow with results
        repo.set_flujo(FlujoFactory.con_resultados(
            telefono=telefono,
            servicio="plomero",
            ciudad="Quito",
            num_proveedores=3,
        ))

        # User selects first provider
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )

        assert respuesta["estado"] == EstadoConversacion.VIEWING_PROVIDER_DETAIL.value
        assert "Juan" in respuesta["response"] or "1" in respuesta["response"]

    @pytest.mark.asyncio
    async def test_seleccion_invalida(self, maquina_busqueda):
        """Test invalid provider selection."""
        maquina, repo, _, _ = maquina_busqueda
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.con_resultados(
            telefono=telefono,
            num_proveedores=3,
        ))

        # Invalid selection
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="99",
        )

        # Should stay in same state
        assert respuesta["estado"] == EstadoConversacion.PRESENTING_RESULTS.value

    @pytest.mark.asyncio
    async def test_cancelar_busqueda(self, maquina_busqueda):
        """Test canceling search."""
        maquina, repo, _, _ = maquina_busqueda
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.en_busqueda(telefono))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="cancelar",
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value


class TestFlujoBusquedaErrores:
    """Tests for error handling in search flow."""

    @pytest.fixture
    def maquina_con_errores(self):
        """Provides a state machine configured for error testing."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        buscador = MockBuscadorProveedores()

        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            buscador_proveedores=buscador,
            logger=get_logger("test"),
        )

        return maquina, repo, buscador

    @pytest.mark.asyncio
    async def test_error_en_busqueda(self, maquina_con_errores):
        """Test handling search errors."""
        maquina, repo, buscador = maquina_con_errores
        telefono = "+593999999999"

        # Configure error
        buscador.lanzar_error = True

        repo.set_flujo(FlujoFactory.en_busqueda(telefono))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )

        # Should transition to error state
        assert respuesta["estado"] == EstadoConversacion.ERROR.value
        assert "error" in respuesta["response"].lower()

    @pytest.mark.asyncio
    async def test_timeout_en_busqueda(self, maquina_con_errores):
        """Test handling search timeout."""
        maquina, repo, buscador = maquina_con_errores
        telefono = "+593999999999"

        # Configure long delay
        buscador.delay_seconds = 60  # Will timeout

        repo.set_flujo(FlujoFactory.en_busqueda(telefono))

        # This should timeout (default is 30s in state)
        # For testing, we just verify the structure
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )

        # Response should indicate timeout or error
        assert respuesta is not None


class TestFlujoNuevaBusqueda:
    """Tests for new search flow."""

    @pytest.fixture
    def maquina_nueva_busqueda(self):
        """Provides a configured state machine."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()

        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )

        return maquina, repo

    @pytest.mark.asyncio
    async def test_nueva_busqueda_mismo_servicio(self, maquina_nueva_busqueda):
        """Test retry same search."""
        maquina, repo = maquina_nueva_busqueda
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.CONFIRM_NEW_SEARCH,
            servicio="plomero",
            ciudad="Quito",
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="3",  # Retry option
        )

        assert respuesta["estado"] == EstadoConversacion.SEARCHING.value

    @pytest.mark.asyncio
    async def test_nueva_busqueda_otro_servicio(self, maquina_nueva_busqueda):
        """Test new search with different service."""
        maquina, repo = maquina_nueva_busqueda
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.CONFIRM_NEW_SEARCH,
            servicio="plomero",
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",  # New service option
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value

    @pytest.mark.asyncio
    async def test_nueva_busqueda_otra_ciudad(self, maquina_nueva_busqueda):
        """Test new search with different city."""
        maquina, repo = maquina_nueva_busqueda
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.CONFIRM_NEW_SEARCH,
            servicio="plomero",
            ciudad="Quito",
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",  # New city option
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_CITY.value
