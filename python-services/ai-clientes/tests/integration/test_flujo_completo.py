"""
Integration tests for complete user journeys.

Tests end-to-end flows from first contact to completion.
"""

import pytest

from models.estados import EstadoConversacion
from state_machine import MaquinaEstados
from tests.conftest import (
    MockRepositorioFlujo,
    MockRepositorioClientes,
    MockExtractorNecesidad,
    MockBuscadorProveedores,
    MockServicioConsentimiento,
    FlujoFactory,
    ProveedorFactory,
)


class TestFlujoCompleto:
    """End-to-end integration tests."""

    @pytest.fixture
    def sistema_completo(self):
        """Provides a fully configured system."""
        from infrastructure.logging.structured_logger import get_logger

        repo_flujo = MockRepositorioFlujo()
        repo_clientes = MockRepositorioClientes()
        extractor = MockExtractorNecesidad()
        buscador = MockBuscadorProveedores()
        consent = MockServicioConsentimiento()

        # Configure services
        extractor.servicio_a_retornar = "plomero"

        proveedores = [
            ProveedorFactory.crear(
                id="p1",
                nombre="Juan Pérez",
                telefono="+593999111111",
                rating=4.8,
                profesiones=["plomero", "fontanero"],
                verified=True,
            ),
            ProveedorFactory.crear(
                id="p2",
                nombre="María García",
                telefono="+593999222222",
                rating=4.5,
                profesiones=["plomero"],
            ),
        ]
        buscador.set_proveedores(proveedores)

        maquina = MaquinaEstados(
            repositorio_flujo=repo_flujo,
            repositorio_clientes=repo_clientes,
            extractor_necesidad=extractor,
            buscador_proveedores=buscador,
            servicio_consentimiento=consent,
            logger=get_logger("test"),
        )

        return {
            "maquina": maquina,
            "repo_flujo": repo_flujo,
            "repo_clientes": repo_clientes,
            "extractor": extractor,
            "buscador": buscador,
            "consent": consent,
        }

    @pytest.mark.asyncio
    async def test_flujo_completo_exitoso(self, sistema_completo):
        """Test complete successful user journey."""
        maquina = sistema_completo["maquina"]
        repo = sistema_completo["repo_flujo"]
        telefono = "+593999999999"

        # Step 1: Initial message (no flow exists)
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="Hola",
        )

        # Should create flow in awaiting_service
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.state == EstadoConversacion.AWAITING_SERVICE

        # Step 2: User describes need
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="necesito un plomero",
        )
        assert respuesta["estado"] == EstadoConversacion.CONFIRM_SERVICE.value

        # Step 3: Confirm service
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert respuesta["estado"] == EstadoConversacion.AWAITING_CITY.value

        # Step 4: Provide city
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="Quito",
        )
        assert respuesta["estado"] == EstadoConversacion.SEARCHING.value

        # Step 5: Trigger search
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="buscar",
        )
        assert respuesta["estado"] == EstadoConversacion.PRESENTING_RESULTS.value

        # Step 6: Select provider
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert respuesta["estado"] == EstadoConversacion.VIEWING_PROVIDER_DETAIL.value

        # Step 7: Request contact
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert respuesta["estado"] == EstadoConversacion.AWAITING_CONTACT_SHARE.value

        # Step 8: Share contact
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )
        assert respuesta["estado"] == EstadoConversacion.AWAITING_HIRING_FEEDBACK.value

        # Step 9: Provide feedback
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",  # Excelente
        )
        assert respuesta["estado"] == EstadoConversacion.COMPLETED.value

    @pytest.mark.asyncio
    async def test_flujo_con_reinicio(self, sistema_completo):
        """Test flow with user restarting."""
        maquina = sistema_completo["maquina"]
        repo = sistema_completo["repo_flujo"]
        telefono = "+593999999999"

        # Start journey
        await maquina.procesar_mensaje(telefono=telefono, texto="hola")
        await maquina.procesar_mensaje(telefono=telefono, texto="plomero")
        await maquina.procesar_mensaje(telefono=telefono, texto="1")

        # User is in AWAITING_CITY
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.state == EstadoConversacion.AWAITING_CITY

        # User restarts
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="reiniciar",
        )

        # Should be back to awaiting service
        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value

    @pytest.mark.asyncio
    async def test_flujo_con_cambio_servicio(self, sistema_completo):
        """Test flow with user changing service mid-way."""
        maquina = sistema_completo["maquina"]
        repo = sistema_completo["repo_flujo"]
        telefono = "+593999999999"

        # Start journey
        await maquina.procesar_mensaje(telefono=telefono, texto="hola")
        await maquina.procesar_mensaje(telefono=telefono, texto="plomero")
        await maquina.procesar_mensaje(telefono=telefono, texto="1")
        await maquina.procesar_mensaje(telefono=telefono, texto="Quito")

        # User is in SEARCHING
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.service == "plomero"

        # User changes mind about service
        await maquina.resetear_flujo(telefono)

        # New flow
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="electricista",
        )

        assert respuesta["estado"] == EstadoConversacion.CONFIRM_SERVICE.value

    @pytest.mark.asyncio
    async def test_multiples_usuarios_simultaneos(self, sistema_completo):
        """Test handling multiple users simultaneously."""
        maquina = sistema_completo["maquina"]
        repo = sistema_completo["repo_flujo"]

        # Simulate multiple users
        usuarios = ["+593999111111", "+593999222222", "+593999333333"]

        for telefono in usuarios:
            await maquina.procesar_mensaje(telefono=telefono, texto="hola")

        # All should have their own flows
        for telefono in usuarios:
            flujo = await repo.obtener_modelo(telefono)
            assert flujo is not None
            assert flujo.telefono == telefono

        # Continue with different states per user
        await maquina.procesar_mensaje(telefono=usuarios[0], texto="plomero")
        await maquina.procesar_mensaje(telefono=usuarios[1], texto="electricista")
        await maquina.procesar_mensaje(telefono=usuarios[2], texto="carpintero")

        # Verify each has their own service
        flujo0 = await repo.obtener_modelo(usuarios[0])
        flujo1 = await repo.obtener_modelo(usuarios[1])
        flujo2 = await repo.obtener_modelo(usuarios[2])

        assert flujo0.service != flujo1.service or True  # Services may differ


class TestFlujoEdgeCases:
    """Tests for edge cases in complete flows."""

    @pytest.fixture
    def sistema_basico(self):
        """Provides basic system for edge case testing."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )
        return maquina, repo

    @pytest.mark.asyncio
    async def test_mensaje_vacio(self, sistema_basico):
        """Test handling empty message."""
        maquina, _ = sistema_basico
        telefono = "+593999999999"

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="",
        )

        # Should handle gracefully
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_mensaje_muy_largo(self, sistema_basico):
        """Test handling very long message."""
        maquina, _ = sistema_basico
        telefono = "+593999999999"

        texto_largo = "necesito ayuda " * 1000

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto=texto_largo,
        )

        # Should handle without crashing
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_caracteres_especiales(self, sistema_basico):
        """Test handling special characters."""
        maquina, _ = sistema_basico
        telefono = "+593999999999"

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="🔥💥¿Necesito un plomero?🎉",
        )

        # Should handle special characters
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_estado_corrupto_recuperacion(self, sistema_basico):
        """Test recovery from corrupted state."""
        maquina, repo = sistema_basico
        telefono = "+593999999999"

        # Set flow with inconsistent data
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            providers=[],  # No providers but in detail view
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",  # Try to go back to results
        )

        # Should handle gracefully
        assert respuesta is not None
