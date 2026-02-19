"""
Shared pytest fixtures for ai-clientes tests.

This module provides fixtures for:
- Mocked repositories (Redis, Supabase)
- Mocked services (AI extractor, search)
- Test data factories
- Async test configuration
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.estados import EstadoConversacion, FlujoConversacional


# Configure pytest for async
@pytest.fixture(scope="session")
def event_loop():
    """Creates an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# TEST DATA FACTORIES
# ============================================================


@dataclass
class FlujoFactory:
    """Factory for creating test FlujoConversacional instances."""

    @staticmethod
    def crear(
        telefono: str = "+593999999999",
        estado: EstadoConversacion = EstadoConversacion.AWAITING_SERVICE,
        servicio: Optional[str] = None,
        ciudad: Optional[str] = None,
        proveedores: Optional[List[Dict]] = None,
        **kwargs,
    ) -> FlujoConversacional:
        """Creates a FlujoConversacional with defaults."""
        # Handle both naming conventions for flexibility
        if "providers" not in kwargs:
            kwargs["providers"] = proveedores or []
        if "service" not in kwargs and servicio is not None:
            kwargs["service"] = servicio
        if "city" not in kwargs and ciudad is not None:
            kwargs["city"] = ciudad
        return FlujoConversacional(
            telefono=telefono,
            state=estado,
            **kwargs,
        )

    @staticmethod
    def en_consentimiento(telefono: str = "+593999999999") -> FlujoConversacional:
        """Creates a flow in awaiting_consent state."""
        return FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_CONSENT,
        )

    @staticmethod
    def en_servicio(telefono: str = "+593999999999") -> FlujoConversacional:
        """Creates a flow in awaiting_service state."""
        return FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_SERVICE,
        )

    @staticmethod
    def en_ciudad(
        telefono: str = "+593999999999",
        servicio: str = "plomero",
    ) -> FlujoConversacional:
        """Creates a flow in awaiting_city state."""
        return FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.AWAITING_CITY,
            servicio=servicio,
        )

    @staticmethod
    def en_busqueda(
        telefono: str = "+593999999999",
        servicio: str = "plomero",
        ciudad: str = "Quito",
    ) -> FlujoConversacional:
        """Creates a flow in searching state."""
        return FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.SEARCHING,
            servicio=servicio,
            ciudad=ciudad,
        )

    @staticmethod
    def con_resultados(
        telefono: str = "+593999999999",
        servicio: str = "plomero",
        ciudad: str = "Quito",
        num_proveedores: int = 3,
    ) -> FlujoConversacional:
        """Creates a flow with provider results."""
        proveedores = [
            {
                "id": f"prov-{i}",
                "name": f"Proveedor {i}",
                "phone_number": f"+59399999999{i}",
                "rating": 4.5,
                "city": ciudad,
            }
            for i in range(num_proveedores)
        ]
        return FlujoFactory.crear(
            telefono=telefono,
            estado=EstadoConversacion.PRESENTING_RESULTS,
            servicio=servicio,
            ciudad=ciudad,
            proveedores=proveedores,
        )


@dataclass
class ProveedorFactory:
    """Factory for creating test provider data."""

    @staticmethod
    def crear(
        id: str = "prov-1",
        nombre: str = "Juan Pérez",
        telefono: str = "+593999999999",
        ciudad: str = "Quito",
        rating: float = 4.5,
        profesiones: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Creates a provider dict with defaults."""
        return {
            "id": id,
            "name": nombre,
            "full_name": nombre,
            "phone_number": telefono,
            "real_phone": telefono,
            "city": ciudad,
            "rating": rating,
            "professions": profesiones or ["plomero"],
            "services": kwargs.get("services", []),
            "verified": kwargs.get("verified", False),
            "years_of_experience": kwargs.get("years_of_experience", 5),
            **kwargs,
        }


# ============================================================
# MOCK REPOSITORIES
# ============================================================


class MockRepositorioFlujo:
    """Mock implementation of IRepositorioFlujo."""

    def __init__(self):
        self._flows: Dict[str, FlujoConversacional] = {}
        self.guardar_llamado = False
        self.resetear_llamado = False

    async def obtener(self, telefono: str) -> Dict[str, Any]:
        """Gets flow as dict."""
        flujo = self._flows.get(telefono)
        return flujo.to_dict() if flujo else {}

    async def obtener_modelo(self, telefono: str) -> Optional[FlujoConversacional]:
        """Gets flow as model."""
        return self._flows.get(telefono)

    async def guardar(self, telefono: str, datos: Dict[str, Any]) -> None:
        """Saves flow from dict."""
        self.guardar_llamado = True
        self._flows[telefono] = FlujoConversacional.from_dict(datos)

    async def guardar_modelo(self, flujo: FlujoConversacional) -> None:
        """Saves flow model."""
        self.guardar_llamado = True
        self._flows[flujo.telefono] = flujo

    async def resetear(self, telefono: str) -> None:
        """Resets flow."""
        self.resetear_llamado = True
        self._flows.pop(telefono, None)

    def set_flujo(self, flujo: FlujoConversacional) -> None:
        """Sets a flow directly for testing."""
        self._flows[flujo.telefono] = flujo


class MockRepositorioClientes:
    """Mock implementation of IRepositorioClientes."""

    def __init__(self):
        self._clientes: Dict[str, Dict[str, Any]] = {}

    async def obtener_o_crear(
        self, telefono: str, nombre: Optional[str] = None
    ) -> Dict[str, Any]:
        """Gets or creates a customer."""
        if telefono not in self._clientes:
            self._clientes[telefono] = {
                "id": f"cliente-{telefono}",
                "telefono": telefono,
                "nombre": nombre,
            }
        return self._clientes[telefono]

    async def actualizar_ciudad(self, cliente_id: str, ciudad: str) -> Dict[str, Any]:
        """Updates customer city."""
        for cliente in self._clientes.values():
            if cliente.get("id") == cliente_id:
                cliente["city"] = ciudad
                return cliente
        return {}

    async def actualizar_consentimiento(
        self, cliente_id: str, tiene_consentimiento: bool
    ) -> bool:
        """Updates customer consent."""
        for cliente in self._clientes.values():
            if cliente.get("id") == cliente_id:
                cliente["has_consent"] = tiene_consentimiento
                return True
        return False


# ============================================================
# MOCK SERVICES
# ============================================================


class MockExtractorNecesidad:
    """Mock AI need extractor."""

    def __init__(self):
        self.servicio_a_retornar: Optional[str] = "plomero"
        self.ciudad_a_retornar: Optional[str] = None
        self.lanzar_error = False

    async def extraer(self, texto: str) -> Dict[str, Any]:
        """Extracts service and city from text."""
        if self.lanzar_error:
            raise Exception("Error de extracción simulado")

        return {
            "servicio": self.servicio_a_retornar,
            "ciudad": self.ciudad_a_retornar,
            "confianza": 0.9,
        }


class MockBuscadorProveedores:
    """Mock provider search service."""

    def __init__(self):
        self._proveedores: List[Dict[str, Any]] = []
        self.lanzar_error = False
        self.delay_seconds = 0

    def set_proveedores(self, proveedores: List[Dict[str, Any]]) -> None:
        """Sets providers to return."""
        self._proveedores = proveedores

    async def buscar(
        self,
        servicio: str,
        ciudad: str,
        limite: int = 10,
    ) -> Dict[str, Any]:
        """Searches for providers."""
        if self.lanzar_error:
            raise Exception("Error de búsqueda simulado")

        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)

        return {
            "proveedores": self._proveedores[:limite],
            "total": len(self._proveedores),
            "servicio": servicio,
            "ciudad": ciudad,
        }


class MockServicioConsentimiento:
    """Mock consent management service."""

    def __init__(self):
        self._consents: Dict[str, bool] = {}

    async def registrar_consentimiento(self, cliente_id: str, aceptado: bool) -> None:
        """Records consent."""
        self._consents[cliente_id] = aceptado

    def tiene_consentimiento(self, cliente_id: str) -> bool:
        """Checks if consent was given."""
        return self._consents.get(cliente_id, False)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def flujo_factory() -> FlujoFactory:
    """Provides the flujo factory."""
    return FlujoFactory()


@pytest.fixture
def proveedor_factory() -> ProveedorFactory:
    """Provides the provider factory."""
    return ProveedorFactory()


@pytest.fixture
def mock_repositorio_flujo() -> MockRepositorioFlujo:
    """Provides a mock flow repository."""
    return MockRepositorioFlujo()


@pytest.fixture
def mock_repositorio_clientes() -> MockRepositorioClientes:
    """Provides a mock customer repository."""
    return MockRepositorioClientes()


@pytest.fixture
def mock_extractor_necesidad() -> MockExtractorNecesidad:
    """Provides a mock need extractor."""
    return MockExtractorNecesidad()


@pytest.fixture
def mock_buscador_proveedores() -> MockBuscadorProveedores:
    """Provides a mock provider search service."""
    return MockBuscadorProveedores()


@pytest.fixture
def mock_servicio_consentimiento() -> MockServicioConsentimiento:
    """Provides a mock consent service."""
    return MockServicioConsentimiento()


@pytest.fixture
def mock_logger() -> MagicMock:
    """Provides a mock logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def mock_enviar_mensaje() -> AsyncMock:
    """Provides a mock send message callback."""
    return AsyncMock()


@pytest.fixture
def mock_actualizar_ciudad() -> AsyncMock:
    """Provides a mock update city callback."""
    return AsyncMock()
