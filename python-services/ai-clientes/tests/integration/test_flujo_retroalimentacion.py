"""
Integration tests for feedback flow.

Tests the feedback collection after provider contact.
"""

import pytest

from models.estados import EstadoConversacion
from state_machine import MaquinaEstados
from tests.conftest import (
    MockRepositorioFlujo,
    FlujoFactory,
    ProveedorFactory,
)


class TestFlujoRetroalimentacion:
    """Integration tests for feedback flow."""

    @pytest.fixture
    def maquina_feedback(self):
        """Provides a state machine configured for feedback tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )
        return maquina, repo

    @pytest.mark.asyncio
    async def test_flujo_retroalimentacion_completo(self, maquina_feedback):
        """Test complete feedback flow."""
        maquina, repo = maquina_feedback
        telefono = "+593999999999"

        # Set up flow awaiting feedback
        proveedor = ProveedorFactory.crear(nombre="Juan Pérez")
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_HIRING_FEEDBACK,
            chosen_provider=proveedor,
            pending_feedback_provider_name="Juan Pérez",
        ))

        # User provides positive feedback
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",  # Excelente
        )

        assert respuesta["estado"] == EstadoConversacion.COMPLETED.value
        assert "Gracias" in respuesta["response"]

    @pytest.mark.asyncio
    async def test_retroalimentacion_opciones(self, maquina_feedback):
        """Test all feedback options."""
        maquina, repo = maquina_feedback
        telefonos = ["+593999111111", "+593999222222", "+593999333333", "+593999444444"]

        opciones = ["1", "2", "3", "4"]  # Excelente, Buena, Regular, No contactó

        for telefono, opcion in zip(telefonos, opciones):
            proveedor = ProveedorFactory.crear(nombre=f"Proveedor {telefono}")
            repo.set_flujo(FlujoFactory.crear(
                telefono=telefono,
                estado=EstadoConversacion.AWAITING_HIRING_FEEDBACK,
                chosen_provider=proveedor,
            ))

            respuesta = await maquina.procesar_mensaje(
                telefono=telefono,
                texto=opcion,
            )

            assert respuesta["estado"] == EstadoConversacion.COMPLETED.value

    @pytest.mark.asyncio
    async def test_retroalimentacion_invalida(self, maquina_feedback):
        """Test invalid feedback option."""
        maquina, repo = maquina_feedback
        telefono = "+593999999999"

        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_HIRING_FEEDBACK,
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="xyz",  # Invalid
        )

        # Should stay in same state or handle gracefully
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_nueva_busqueda_despues_feedback(self, maquina_feedback):
        """Test starting new search after feedback."""
        maquina, repo = maquina_feedback
        telefono = "+593999999999"

        # Complete feedback flow
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_HIRING_FEEDBACK,
        ))

        await maquina.procesar_mensaje(telefono=telefono, texto="1")

        # User wants new search
        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",  # Nueva búsqueda
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value


class TestFlujoContacto:
    """Tests for contact sharing flow."""

    @pytest.fixture
    def maquina_contacto(self):
        """Provides a state machine for contact tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )
        return maquina, repo

    @pytest.mark.asyncio
    async def test_compartir_contacto_aceptado(self, maquina_contacto):
        """Test accepting contact sharing."""
        maquina, repo = maquina_contacto
        telefono = "+593999999999"

        proveedor = ProveedorFactory.crear(
            nombre="Juan Pérez",
            telefono="+593999111111",
        )
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_CONTACT_SHARE,
            chosen_provider=proveedor,
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="1",  # Aceptar compartir
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_HIRING_FEEDBACK.value
        assert "compartido" in respuesta["response"].lower()

    @pytest.mark.asyncio
    async def test_compartir_contacto_rechazado(self, maquina_contacto):
        """Test declining contact sharing."""
        maquina, repo = maquina_contacto
        telefono = "+593999999999"

        proveedor = ProveedorFactory.crear(nombre="Juan Pérez")
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_CONTACT_SHARE,
            chosen_provider=proveedor,
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",  # Rechazar compartir
        )

        # Should go back to provider detail or results
        assert respuesta["estado"] in [
            EstadoConversacion.VIEWING_PROVIDER_DETAIL.value,
            EstadoConversacion.PRESENTING_RESULTS.value,
        ]

    @pytest.mark.asyncio
    async def test_ver_otro_proveedor_despues_contacto(self, maquina_contacto):
        """Test viewing another provider after contact options."""
        maquina, repo = maquina_contacto
        telefono = "+593999999999"

        proveedores = [
            ProveedorFactory.crear(id="p1", nombre="Juan Pérez"),
            ProveedorFactory.crear(id="p2", nombre="María García"),
        ]
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_CONTACT_SHARE,
            chosen_provider=proveedores[0],
            providers=proveedores,
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",  # Ver otro proveedor
        )

        # Should go back to viewing or results
        assert respuesta["estado"] in [
            EstadoConversacion.VIEWING_PROVIDER_DETAIL.value,
            EstadoConversacion.PRESENTING_RESULTS.value,
        ]


class TestFlujoProviderDetail:
    """Tests for provider detail interactions."""

    @pytest.fixture
    def maquina_detalle(self):
        """Provides state machine for detail tests."""
        from infrastructure.logging.structured_logger import get_logger

        repo = MockRepositorioFlujo()
        maquina = MaquinaEstados(
            repositorio_flujo=repo,
            logger=get_logger("test"),
        )
        return maquina, repo

    @pytest.mark.asyncio
    async def test_ver_detalle_proveedor(self, maquina_detalle):
        """Test viewing provider detail."""
        maquina, repo = maquina_detalle
        telefono = "+593999999999"

        proveedor = ProveedorFactory.crear(
            nombre="Juan Pérez",
            ciudad="Quito",
            rating=4.8,
            profesiones=["plomero", "fontanero"],
            years_of_experience=10,
            verified=True,
        )
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            chosen_provider=proveedor,
            providers=[proveedor],
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="info",  # Request more info
        )

        # Should stay in detail or handle gracefully
        assert respuesta is not None

    @pytest.mark.asyncio
    async def test_volver_a_resultados(self, maquina_detalle):
        """Test going back to results."""
        maquina, repo = maquina_detalle
        telefono = "+593999999999"

        proveedores = [
            ProveedorFactory.crear(id="p1"),
            ProveedorFactory.crear(id="p2"),
        ]
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            chosen_provider=proveedores[0],
            providers=proveedores,
            service="plomero",
            city="Quito",
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="2",  # Ver otro proveedor
        )

        assert respuesta["estado"] in [
            EstadoConversacion.PRESENTING_RESULTS.value,
            EstadoConversacion.VIEWING_PROVIDER_DETAIL.value,
        ]

    @pytest.mark.asyncio
    async def test_nueva_busqueda_desde_detalle(self, maquina_detalle):
        """Test starting new search from detail view."""
        maquina, repo = maquina_detalle
        telefono = "+593999999999"

        proveedor = ProveedorFactory.crear()
        repo.set_flujo(FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            chosen_provider=proveedor,
        ))

        respuesta = await maquina.procesar_mensaje(
            telefono=telefono,
            texto="3",  # Nueva búsqueda
        )

        assert respuesta["estado"] == EstadoConversacion.AWAITING_SERVICE.value
