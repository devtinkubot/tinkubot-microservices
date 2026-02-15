"""
Unit tests for RepositorioFlujo.

Tests the Redis-based flow repository with Pydantic validation.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models.estados import EstadoConversacion, FlujoConversacional


class MockRedis:
    """Mock Redis client for testing that mimics ClienteRedis behavior."""

    def __init__(self):
        self._data = {}
        self.get_called = False
        self.set_called = False
        self.delete_called = False

    async def get(self, key: str):
        """Get returns parsed JSON like ClienteRedis does."""
        self.get_called = True
        value = self._data.get(key)
        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return None

    async def set(self, key: str, value, ex: int = None, expire: int = None):
        """Set stores as JSON string like ClienteRedis does."""
        self.set_called = True
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        self._data[key] = value
        return True

    async def delete(self, key: str):
        self.delete_called = True
        self._data.pop(key, None)
        return 1


class TestRepositorioFlujo:
    """Tests for RepositorioFlujo."""

    @pytest.fixture
    def mock_redis(self):
        """Provides a mock Redis client."""
        return MockRedis()

    @pytest.fixture
    def repositorio(self, mock_redis):
        """Provides a repository with mock Redis."""
        from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis

        return RepositorioFlujoRedis(
            redis_cliente=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_guardar_flujo(self, repositorio, mock_redis):
        """Test saving a flow."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.AWAITING_SERVICE,
            service="plomero",
        )

        await repositorio.guardar_modelo(flujo)

        assert mock_redis.set_called
        assert "flow:+593999999999" in mock_redis._data

    @pytest.mark.asyncio
    async def test_obtener_flujo_existente(self, repositorio, mock_redis):
        """Test getting an existing flow."""
        import json

        flujo_data = {
            "telefono": "+593999999999",
            "state": "awaiting_service",
            "service": "plomero",
        }
        mock_redis._data["flow:+593999999999"] = json.dumps(flujo_data)

        flujo = await repositorio.obtener_modelo("+593999999999")

        assert flujo is not None
        assert flujo.telefono == "+593999999999"
        assert flujo.service == "plomero"

    @pytest.mark.asyncio
    async def test_obtener_flujo_no_existente(self, repositorio, mock_redis):
        """Test getting a non-existent flow."""
        flujo = await repositorio.obtener_modelo("+593999888888")

        # Should return None or create new
        assert flujo is None or flujo.telefono == "+593999888888"

    @pytest.mark.asyncio
    async def test_resetear_flujo(self, repositorio, mock_redis):
        """Test resetting a flow."""
        import json

        mock_redis._data["flow:+593999999999"] = json.dumps({
            "telefono": "+593999999999",
            "state": "searching",
        })

        await repositorio.resetear("+593999999999")

        assert mock_redis.delete_called

    @pytest.mark.asyncio
    async def test_actualizar_campo(self, repositorio, mock_redis):
        """Test updating a single field."""
        import json

        mock_redis._data["flow:+593999999999"] = json.dumps({
            "telefono": "+593999999999",
            "state": "awaiting_service",
        })

        resultado = await repositorio.actualizar_campo(
            "+593999999999",
            "service",
            "plomero",
        )

        assert resultado.get("service") == "plomero"


class TestRepositorioFlujoValidacion:
    """Tests for Pydantic validation in repository."""

    @pytest.fixture
    def repositorio_con_validacion(self):
        """Provides a repository with validation enabled."""
        from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis

        mock_redis = MockRedis()
        return RepositorioFlujoRedis(
            redis_cliente=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_guardar_valida_schema(self, repositorio_con_validacion):
        """Test that saving validates the schema."""
        flujo = FlujoConversacional(
            telefono="+593999999999",
            state=EstadoConversacion.SEARCHING,
            service="plomero",  # Required for SEARCHING
        )

        # Should not raise
        await repositorio_con_validacion.guardar_modelo(flujo)

    @pytest.mark.asyncio
    async def test_cargar_datos_legacy(self, repositorio_con_validacion):
        """Test loading legacy data without all fields."""
        import json

        # Legacy data might be missing fields
        legacy_data = {
            "telefono": "+593999999999",
            "state": "awaiting_service",
            # Missing: has_consent, city_confirmed, etc.
        }

        mock_redis = repositorio_con_validacion.redis
        mock_redis._data["flow:+593999999999"] = json.dumps(legacy_data)

        # Should handle gracefully with defaults
        flujo = await repositorio_con_validacion.obtener_modelo("+593999999999")

        assert flujo is not None
        assert flujo.has_consent is False  # Default


class TestRepositorioFlujoTransiciones:
    """Tests for state transitions in repository."""

    @pytest.fixture
    def repositorio(self):
        """Provides a repository for transition tests."""
        from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis

        return RepositorioFlujoRedis(
            redis_cliente=MockRedis(),
        )

    @pytest.mark.asyncio
    async def test_transicionar_estado_valido(self, repositorio):
        """Test valid state transition."""
        import json

        mock_redis = repositorio.redis
        mock_redis._data["flow:+593999999999"] = json.dumps({
            "telefono": "+593999999999",
            "state": "awaiting_service",
            "service": "plomero",
        })

        flujo = await repositorio.transicionar_estado(
            "+593999999999",
            EstadoConversacion.AWAITING_CITY,
        )

        assert flujo.state == EstadoConversacion.AWAITING_CITY

    @pytest.mark.asyncio
    async def test_transicionar_estado_invalido(self, repositorio):
        """Test invalid state transition is rejected."""
        import json

        mock_redis = repositorio.redis
        mock_redis._data["flow:+593999999999"] = json.dumps({
            "telefono": "+593999999999",
            "state": "awaiting_service",
        })

        # Can't go directly to presenting_results
        flujo = await repositorio.transicionar_estado(
            "+593999999999",
            EstadoConversacion.PRESENTING_RESULTS,
        )

        # Should return None or keep same state
        assert flujo is None or flujo.state == EstadoConversacion.AWAITING_SERVICE
