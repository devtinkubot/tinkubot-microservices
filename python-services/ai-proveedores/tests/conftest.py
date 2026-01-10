"""
Configuración global de pytest para ai-proveedores.

Este archivo contiene fixtures y configuraciones compartidas entre
todos los tests del proyecto.

Ejecutar tests con:
    pytest tests/ -v
    pytest tests/ -v --cov=.
    pytest tests/ -v -k "test_health"
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Agregar directorio principal al path Python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ========================================================================
# CONFIGURACIÓN DE PYTEST
# ========================================================================

pytest_plugins = ["pytest.asyncio"]


# ========================================================================
# FIXTURES GLOBALES
# ========================================================================


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """
    Retorna el path al directorio de datos de prueba.

    Returns:
        Path: Directorio con fixtures y datos de prueba
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_providers() -> list[dict]:
    """
    Provee datos de ejemplo de proveedores para testing.

    Returns:
        List[Dict]: Lista de proveedores de prueba
    """
    return [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "full_name": "Juan Pérez",
            "profession": "plomero",
            "phone": "+593991234567",
            "email": "juan.perez@email.com",
            "city": "Cuenca",
            "verified": True,
            "available": True,
            "rating": 4.5,
            "services_list": ["plomero", "fontanero"],
        },
        {
            "id": "223e4567-e89b-12d3-a456-426614174001",
            "full_name": "María García",
            "profession": "electricista",
            "phone": "+593992345678",
            "email": "maria.garcia@email.com",
            "city": "Cuenca",
            "verified": True,
            "available": True,
            "rating": 4.8,
            "services_list": ["electricista", "instalaciones"],
        },
        {
            "id": "323e4567-e89b-12d3-a456-426614174002",
            "full_name": "Carlos López",
            "profession": "albañil",
            "phone": "+593993456789",
            "email": "carlos.lopez@email.com",
            "city": "Loja",
            "verified": True,
            "available": False,
            "rating": 4.2,
            "services_list": ["albañileria", "construcción"],
        },
    ]


@pytest.fixture
def mock_redis() -> Mock:
    """
    Mock del cliente de Redis para testing.

    Returns:
        Mock: Cliente de Redis mockeado
    """
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.exists.return_value = False
    return mock


@pytest.fixture
def mock_background_tasks() -> MagicMock:
    """
    Mock de FastAPI BackgroundTasks.

    Returns:
        MagicMock: BackgroundTasks mockeado
    """
    mock = MagicMock()
    mock.add_task = MagicMock()
    return mock


# ========================================================================
# CONFIGURACIÓN DE LOGGING PARA TESTS
# ========================================================================


@pytest.fixture(autouse=True)
def reset_logging() -> None:
    """
    Resetea la configuración de logging antes de cada test.

    Esto evita que logs de tests anteriores afecten tests posteriores.
    """
    import logging

    # Reset all loggers
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith("ai-proveedores") or logger_name == "main":
            logging.getLogger(logger_name).handlers.clear()


# ========================================================================
# CONFIGURACIÓN DE MOCKS EXTERNOS
# ========================================================================


@pytest.fixture(autouse=True)
def mock_external_apis(monkeypatch) -> None:
    """
    Mock automático de APIs externas para todos los tests.

    Previene llamadas reales a:
    - OpenAI API
    - Supabase
    - Redis
    - Servicios HTTP externos
    """
    # Mock de OpenAI
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Test response"))
    ]

    # Mock de httpx
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient = MagicMock()

    # Los tests pueden sobreescribir estos mocks con sus propios fixtures
    #monkeypatch.setattr("main.openai_client", mock_openai)
    #monkeypatch.setattr("main.supabase", MagicMock())


# ========================================================================
# UTILIDADES DE TEST
# ========================================================================


def assert_valid_json_response(response, expected_status_code: int = 200) -> dict:
    """
    Utilidad para validar que una respuesta HTTP es JSON válido.

    Args:
        response: Respuesta HTTP de TestClient
        expected_status_code: Status code esperado (default: 200)

    Returns:
        Dict: JSON parseado de la respuesta

    Raises:
        AssertionError: Si la respuesta no es JSON válida o el status code no coincide
    """
    assert response.status_code == expected_status_code, (
        f"Expected status {expected_status_code}, got {response.status_code}. "
        f"Response: {response.text}"
    )

    try:
        return response.json()
    except Exception as e:
        raise AssertionError(f"Response is not valid JSON: {e}")


def assert_valid_provider_data(provider: dict) -> None:
    """
    Valida que un diccionario de proveedor tenga los campos obligatorios.

    Args:
        provider: Diccionario con datos del proveedor

    Raises:
        AssertionError: Si faltan campos obligatorios
    """
    required_fields = ["id", "full_name", "profession", "phone"]
    for field in required_fields:
        assert field in provider, f"Missing required field: {field}"


def assert_valid_error_response(response, expected_status_code: int = 400) -> dict:
    """
    Valida que una respuesta de error tenga la estructura correcta.

    Args:
        response: Respuesta HTTP de TestClient
        expected_status_code: Status code esperado (default: 400)

    Returns:
        Dict: JSON parseado de la respuesta de error

    Raises:
        AssertionError: Si la respuesta no tiene estructura de error válida
    """
    data = assert_valid_json_response(response, expected_status_code)

    # FastAPI por defecto retorna errores con 'detail'
    assert "detail" in data or "message" in data, (
        f"Error response missing 'detail' or 'message' field. Got: {data}"
    )

    return data
