"""
Unit tests for FlujoConversacional Pydantic model.

Tests validation, transitions, and state management.
"""

import pytest
from datetime import datetime

from models.estados import EstadoConversacion, FlujoConversacional


class TestFlujoConversacionalCreation:
    """Tests for FlujoConversacional creation and validation."""

    def test_creacion_minima(self):
        """Test creating a flow with minimum required fields."""
        flujo = FlujoConversacional(telefono="+593999999999")

        assert flujo.telefono == "+593999999999"
        assert flujo.state == EstadoConversacion.AWAITING_SERVICE
        assert flujo.providers == []
        assert flujo.has_consent is False

    def test_creacion_con_campos_opcionales(self):
        """Test creating a flow with optional fields."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.SEARCHING,
            service="plomero",
            city="Quito",
            customer_id="cliente-123",
            has_consent=True,
        )

        assert flujo.service == "plomero"
        assert flujo.city == "Quito"
        assert flujo.customer_id == "cliente-123"
        assert flujo.has_consent is True

    def test_validacion_telefono_vacio(self):
        """Test that empty phone raises validation error."""
        with pytest.raises(ValueError):
            FlujoConversacional(telefono="")

    def test_normalizacion_telefono(self):
        """Test phone number normalization."""
        flujo = FlujoConversacional(telefono="+593 999 999 999")
        # Normalized to remove spaces
        assert " " not in flujo.telefono


class TestFlujoConversacionalTransitions:
    """Tests for state transitions."""

    def test_puede_transicionar_a_estado_valido(self):
        """Test valid transition check."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.AWAITING_SERVICE,
        )

        assert flujo.puede_transicionar_a(EstadoConversacion.CONFIRM_SERVICE)
        assert flujo.puede_transicionar_a(EstadoConversacion.AWAITING_CITY)

    def test_no_puede_transicionar_a_estado_invalido(self):
        """Test invalid transition check."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.AWAITING_SERVICE,
        )

        # Can't go directly to presenting_results
        assert not flujo.puede_transicionar_a(EstadoConversacion.PRESENTING_RESULTS)

    def test_transicionar_a_exitoso(self):
        """Test successful state transition."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.AWAITING_SERVICE,
            service="plomero",
        )

        nuevo_flujo = flujo.transicionar_a(EstadoConversacion.AWAITING_CITY)

        assert nuevo_flujo.state == EstadoConversacion.AWAITING_CITY
        assert nuevo_flujo.service == "plomero"
        # Original unchanged (immutable)
        assert flujo.state == EstadoConversacion.AWAITING_SERVICE

    def test_transicionar_a_invalido_raise_error(self):
        """Test that invalid transition raises error."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.AWAITING_SERVICE,
        )

        with pytest.raises(ValueError, match="Transición inválida"):
            flujo.transicionar_a(EstadoConversacion.PRESENTING_RESULTS)


class TestFlujoConversacionalMethods:
    """Tests for FlujoConversacional methods."""

    def test_actualizar_campo(self):
        """Test updating a field."""
        flujo = FlujoConversacional(telefono="+593999999999")
        nuevo = flujo.actualizar(service="plomero")

        assert nuevo.service == "plomero"
        assert flujo.service is None  # Original unchanged

    def test_agregar_proveedores(self):
        """Test adding providers."""
        flujo = FlujoConversacional(telefono="+593999999999")
        proveedores = [
            {"id": "1", "name": "Proveedor 1"},
            {"id": "2", "name": "Proveedor 2"},
        ]

        nuevo = flujo.agregar_proveedores(proveedores)

        assert len(nuevo.providers) == 2
        assert nuevo.searching_dispatched is False

    def test_seleccionar_proveedor(self):
        """Test selecting a provider."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            providers=[
                {"id": "1", "name": "Proveedor 1"},
                {"id": "2", "name": "Proveedor 2"},
            ],
        )

        nuevo = flujo.seleccionar_proveedor(0)

        assert nuevo.provider_detail_idx == 0
        assert nuevo.chosen_provider["id"] == "1"

    def test_seleccionar_proveedor_indice_invalido(self):
        """Test selecting with invalid index."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            providers=[{"id": "1", "name": "Proveedor 1"}],
        )

        with pytest.raises(ValueError, match="fuera de rango"):
            flujo.seleccionar_proveedor(5)

    def test_resetear(self):
        """Test resetting flow."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.PRESENTING_RESULTS,
            service="plomero",
            city="Quito",
            providers=[{"id": "1"}],
            customer_id="cliente-123",
            has_consent=True,
        )

        reseteado = flujo.resetear()

        assert reseteado.state == EstadoConversacion.AWAITING_SERVICE
        assert reseteado.service is None
        assert reseteado.providers == []
        # Keep customer data
        assert reseteado.customer_id == "cliente-123"
        assert reseteado.has_consent is True

    def test_to_dict(self):
        """Test serialization to dict."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.SEARCHING,
            service="plomero",
        )

        data = flujo.to_dict()

        assert data["telefono"] == "+593999999999"
        assert data["state"] == EstadoConversacion.SEARCHING
        assert data["service"] == "plomero"

    def test_from_dict_estado_legacy(self):
        """Test deserialization with legacy state."""
        data = {
            "telefono": "+593999999999",
            "state": "unknown_state",  # Legacy/invalid state
        }

        flujo = FlujoConversacional.from_dict(data)

        # Should default to AWAITING_SERVICE
        assert flujo.state == EstadoConversacion.AWAITING_SERVICE


class TestFlujoConversacionalValidation:
    """Tests for model validation."""

    def test_validacion_searching_sin_servicio(self):
        """Test that SEARCHING without service raises error."""
        with pytest.raises(ValueError, match="SEARCHING requiere servicio"):
            FlujoConversacional(
                telefono="+593999999999",
                state=EstadoConversacion.SEARCHING,
                service=None,
            )

    def test_validacion_searching_con_servicio(self):
        """Test that SEARCHING with service is valid."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.SEARCHING,
            service="plomero",
        )
        assert flujo.state == EstadoConversacion.SEARCHING

    def test_validacion_provider_detail_idx_fuera_rango(self):
        """Test that invalid provider_detail_idx raises error."""
        with pytest.raises(ValueError, match="fuera de rango"):
            FlujoConversacional(
                telefono="+593999999999",
                state=EstadoConversacion.VIEWING_PROVIDER_DETAIL,
                providers=[{"id": "1"}],
                provider_detail_idx=5,
            )
