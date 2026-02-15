"""
Integration tests for the consent flow.

Tests the complete consent flow from initial contact
to consent acceptance/rejection.
"""

import pytest

from models.estados import EstadoConversacion
from state_machine import MaquinaEstados
from tests.conftest import (
    MockRepositorioFlujo,
    MockServicioConsentimiento,
    FlujoFactory,
)


class TestFlujoConsentimiento:
    """Integration tests for consent flow."""

    @pytest.fixture
    def maquina_con_consentimiento(self):
        """Provides a state machine with consent service."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        consent = MockServicioConsentimiento()

        return MaquinaEstados(
            repositorio_flujo=repo,
            servicio_consentimiento=consent,
            logger=get_logger("test"),
        ), repo, consent

    @pytest.mark.asyncio
    async def test_flujo_aceptacion_consentimiento(self, maquina_con_consentimiento):
        """Test complete consent acceptance flow."""
        maquina, repo, consent = maquina_con_consentimiento
        telefono = "+593999999999"

        # Set initial state
        repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

        # User accepts
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
            cliente_id="cliente-123",
        )

        assert "Gracias" in respuesta["response"]
        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value

        # Verify flow was updated
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.state == EstadoConversacion.AWAITING_SERVICE
        assert flujo.has_consent is True

        # Verify consent was registered
        assert consent.tiene_consentimiento("cliente-123")

    @pytest.mark.asyncio
    async def test_flujo_rechazo_consentimiento(self, maquina_con_consentimiento):
        """Test complete consent rejection flow."""
        maquina, repo, consent = maquina_con_consentimiento
        telefono = "+593999999999"

        # Set initial state
        repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

        # User rejects
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",
            cliente_id="cliente-123",
        )

        assert "Sin tu consentimiento" in respuesta["response"]
        assert respuesta["estado"] == EstadoConversacion.COMPLETED.value

        # Verify consent was registered as rejected
        assert not consent.tiene_consentimiento("cliente-123")

    @pytest.mark.asyncio
    async def test_respuesta_invalida_mantiene_estado(self, maquina_con_consentimiento):
        """Test invalid response keeps user in consent state."""
        maquina, repo, _ = maquina_con_consentimiento
        telefono = "+593999999999"

        # Set initial state
        repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

        # Invalid response
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="xyz123",
        )

        assert "1" in respuesta["response"] or "2" in respuesta["response"]

        # Verify state didn't change
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.state == EstadoConversacion.AWAITING_CONSENT

    @pytest.mark.asyncio
    async def test_multiples_intentos_invalidos(self, maquina_con_consentimiento):
        """Test multiple invalid attempts before success."""
        maquina, repo, _ = maquina_con_consentimiento
        telefono = "+593999999999"

        # Set initial state
        repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

        # Multiple invalid attempts
        for _ in range(3):
            await maquina.procesar_mensaje(telefono=telefono, texto="invalid")

        # Verify still in consent state
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.state == EstadoConversacion.AWAITING_CONSENT

        # Valid response
        respuesta = await maquina.procesar_mensaje(telefono=telefono, texto="acepto")

        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value

    @pytest.mark.asyncio
    async def test_variaciones_de_aceptacion(self, maquina_con_consentimiento):
        """Test various acceptance keywords work."""
        maquina, repo, _ = maquina_con_consentimiento

        keywords_aceptacion = ["1", "acepto", "si", "sí", "ok", "yes"]

        for i, keyword in enumerate(keywords_aceptacion):
            # Use numeric suffix to avoid phone normalization collisions
            telefono = f"+5939999999{i:02d}"
            repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

            respuesta = await maquina.procesar_mensaje(
                telefono=telefono,
                texto=keyword,
            )

            assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value, \
                f"Keyword '{keyword}' should transition to AWAITING_SERVICE"


class TestFlujoConsentimientoSinServicio:
    """Tests for consent flow when consent service is unavailable."""

    @pytest.fixture
    def maquina_sin_consentimiento(self):
        """Provides a state machine without consent service."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()

        return MaquinaEstados(
            repositorio_flujo=repo,
            servicio_consentimiento=None,  # No consent service
            logger=get_logger("test"),
        ), repo

    @pytest.mark.asyncio
    async def test_aceptacion_funciona_sin_servicio(self, maquina_sin_consentimiento):
        """Test acceptance works even without consent service."""
        maquina, repo = maquina_sin_consentimiento
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.en_consentimiento(telefono))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",
        )

        # Should still transition successfully
        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value

        # Flow should be updated
        flujo = await repo.obtener_modelo(telefono)
        assert flujo.has_consent is True
