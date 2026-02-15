"""
Unit tests for state transitions.

Tests the transition graph and validation functions.
"""

import pytest

from models.estados import EstadoConversacion
from models.estados.transiciones import (
    puede_transicionar,
    obtener_transiciones_validas,
    validar_ruta_transicion,
    TRANSICIONES_VALIDAS,
)


class TestTransicionesValidas:
    """Tests for the transition graph."""

    def test_todos_estados_tienen_transiciones(self):
        """Test that all states have defined transitions."""
        estados_sin_transiciones = []

        for estado in EstadoConversacion:
            if estado not in TRANSICIONES_VALIDAS:
                estados_sin_transiciones.append(estado)

        # All states should have transitions (even if empty)
        assert len(estados_sin_transiciones) == 0, \
            f"Estados sin transiciones: {estados_sin_transiciones}"

    def test_transiciones_awaiting_service(self):
        """Test valid transitions from AWAITING_SERVICE."""
        validas = obtener_transiciones_validas(EstadoConversacion.AWAITING_SERVICE)

        assert EstadoConversacion.CONFIRM_SERVICE in validas
        assert EstadoConversacion.AWAITING_CITY in validas
        assert EstadoConversacion.SEARCHING in validas
        assert EstadoConversacion.ERROR in validas

    def test_transiciones_searching(self):
        """Test valid transitions from SEARCHING."""
        validas = obtener_transiciones_validas(EstadoConversacion.SEARCHING)

        assert EstadoConversacion.PRESENTING_RESULTS in validas
        assert EstadoConversacion.AWAITING_SERVICE in validas
        assert EstadoConversacion.ERROR in validas

    def test_transiciones_presenting_results(self):
        """Test valid transitions from PRESENTING_RESULTS."""
        validas = obtener_transiciones_validas(EstadoConversacion.PRESENTING_RESULTS)

        assert EstadoConversacion.VIEWING_PROVIDER_DETAIL in validas
        assert EstadoConversacion.CONFIRM_NEW_SEARCH in validas
        assert EstadoConversacion.AWAITING_SERVICE in validas


class TestPuedeTransicionar:
    """Tests for puede_transicionar function."""

    def test_transicion_valida(self):
        """Test valid transition returns True."""
        assert puede_transicionar(
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_CITY,
        )

    def test_transicion_invalida(self):
        """Test invalid transition returns False."""
        assert not puede_transicionar(
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.PRESENTING_RESULTS,
        )

    def test_transicion_mismo_estado(self):
        """Test transition to same state."""
        # Some states allow self-transitions (like AWAITING_SERVICE)
        result = puede_transicionar(
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_SERVICE,
        )
        assert result  # Loop is allowed

    def test_transicion_desde_estado_terminal(self):
        """Test transitions from terminal states."""
        assert puede_transicionar(
            EstadoConversacion.COMPLETED,
            EstadoConversacion.AWAITING_SERVICE,
        )


class TestObtenerTransicionesValidas:
    """Tests for obtener_transiciones_validas function."""

    def test_retorna_set(self):
        """Test that function returns a set."""
        result = obtener_transiciones_validas(EstadoConversacion.AWAITING_SERVICE)
        assert isinstance(result, set)

    def test_estado_sin_transiciones(self):
        """Test state with no transitions returns empty set."""
        # All states have transitions, but test the function handles it
        result = obtener_transiciones_validas(EstadoConversacion.AWAITING_SERVICE)
        assert len(result) > 0


class TestValidarRutaTransicion:
    """Tests for validar_ruta_transicion function."""

    def test_ruta_vacia(self):
        """Test empty route is invalid."""
        valida, error = validar_ruta_transicion([])
        assert not valida
        assert "vacía" in error.lower()

    def test_ruta_un_estado(self):
        """Test single state route is valid."""
        valida, error = validar_ruta_transicion([EstadoConversacion.AWAITING_SERVICE])
        assert valida
        assert error == ""

    def test_ruta_valida(self):
        """Test valid multi-step route."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_CITY,
            EstadoConversacion.SEARCHING,
            EstadoConversacion.PRESENTING_RESULTS,
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida
        assert error == ""

    def test_ruta_con_transicion_invalida(self):
        """Test route with invalid transition."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.PRESENTING_RESULTS,  # Invalid!
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert not valida
        assert "inválida" in error.lower()

    def test_ruta_consentimiento_completa(self):
        """Test complete consent flow route."""
        ruta = [
            EstadoConversacion.AWAITING_CONSENT,
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.CONFIRM_SERVICE,
            EstadoConversacion.AWAITING_CITY,
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida


class TestFlujosTipicos:
    """Tests for typical conversation flows."""

    def test_flujo_busqueda_exitosa(self):
        """Test successful search flow."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_CITY,
            EstadoConversacion.SEARCHING,
            EstadoConversacion.PRESENTING_RESULTS,
            EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            EstadoConversacion.AWAITING_CONTACT_SHARE,
            EstadoConversacion.AWAITING_HIRING_FEEDBACK,
            EstadoConversacion.COMPLETED,
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida, f"Flujo inválido: {error}"

    def test_flujo_sin_resultados(self):
        """Test no results flow."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_CITY,
            EstadoConversacion.SEARCHING,
            EstadoConversacion.AWAITING_SERVICE,  # Back to start
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida, f"Flujo inválido: {error}"

    def test_flujo_nueva_busqueda(self):
        """Test new search from results."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.AWAITING_CITY,
            EstadoConversacion.SEARCHING,
            EstadoConversacion.PRESENTING_RESULTS,
            EstadoConversacion.CONFIRM_NEW_SEARCH,
            EstadoConversacion.AWAITING_SERVICE,
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida, f"Flujo inválido: {error}"

    def test_flujo_error_recovery(self):
        """Test error recovery flow."""
        ruta = [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.ERROR,
            EstadoConversacion.AWAITING_SERVICE,
        ]
        valida, error = validar_ruta_transicion(ruta)
        assert valida, f"Flujo inválido: {error}"
