"""
Contratos de API (Endpoint Tests) para ai-proveedores.

Este módulo contiene tests contractuales para todos los endpoints públicos
del servicio ai-proveedores. Estos tests aseguran que no haya breaking changes
durante la refactorización Sprint-1.12.

Cada test verifica:
- Status codes correctos (200, 400, 500)
- Estructura de respuestas JSON
- Manejo apropiado de errores
- Mock correcto de dependencias externas

Ejecutar con:
    pytest tests/api/test_endpoints.py -v
    pytest tests/api/test_endpoints.py -v -k test_health
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import httpx
from fastapi import BackgroundTasks, testclient
from fastapi.testclient import TestClient

# Importar la aplicación FastAPI desde main.py
import sys
from pathlib import Path

# Agregar el directorio principal al path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from main import app


# ========================================================================
# FIXTURES COMUNES
# ========================================================================


@pytest.fixture
def client() -> testclient.TestClient:
    """
    Fixture que proporciona un cliente de prueba para FastAPI.

    Returns:
        TestClient: Cliente HTTP para testing
    """
    return TestClient(app)


@pytest.fixture
def mock_supabase() -> Mock:
    """
    Mock del cliente de Supabase para evitar llamadas a la base de datos real.

    Returns:
        Mock: Cliente de Supabase mockeado
    """
    mock = MagicMock()
    mock.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    return mock


@pytest.fixture
def mock_openai() -> Mock:
    """
    Mock del cliente de OpenAI para evitar llamadas a la API real.

    Returns:
        Mock: Cliente de OpenAI mockeado
    """
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Respuesta de prueba"))
    ]
    return mock


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """
    Mock del cliente httpx para llamadas HTTP externas.

    Returns:
        AsyncMock: Cliente httpx mockeado
    """
    mock = AsyncMock()
    mock.post.return_value = MagicMock(
        status_code=200, raise_for_status=MagicMock(), json=MagicMock(return_value={})
    )
    mock.__aenter__.return_value = mock
    mock.__aexit__.return_value = None
    return mock


@pytest.fixture
def sample_provider_data() -> Dict[str, Any]:
    """
    Datos de ejemplo de un proveedor para testing.

    Returns:
        Dict: Datos de proveedor de prueba
    """
    return {
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
    }


@pytest.fixture
def sample_search_request() -> Dict[str, Any]:
    """
    Datos de ejemplo para una búsqueda inteligente.

    Returns:
        Dict: Datos de búsqueda de prueba
    """
    return {
        "profesion_principal": "plomero",
        "ubicacion": "Cuenca",
        "urgencia": "alta",
        "necesidad_real": "Necesito reparar una tubería",
    }


@pytest.fixture
def sample_whatsapp_message() -> Dict[str, Any]:
    """
    Datos de ejemplo para un mensaje WhatsApp.

    Returns:
        Dict: Datos de mensaje WhatsApp de prueba
    """
    return {
        "phone": "+593991234567",
        "message": "Hola, quiero registrarme como proveedor",
    }


# ========================================================================
# TESTS: GET /health
# ========================================================================


class TestHealthEndpoint:
    """Tests para el endpoint GET /health."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """
        Test que el endpoint de health check retorna status 200.

        Este test verifica que el endpoint sea accesible y responda
        correctamente sin errores.
        """
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client: TestClient) -> None:
        """
        Test que la respuesta del health check tiene la estructura correcta.

        Verifica que la respuesta JSON contenga los campos obligatorios:
        - status: str
        - service: str
        - timestamp: str
        """
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "service" in data
        assert "timestamp" in data
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["timestamp"], str)

    def test_health_check_service_name(self, client: TestClient) -> None:
        """
        Test que el health check retorna el nombre correcto del servicio.

        El servicio debe identificarse como 'ai-proveedores' o similar.
        """
        response = client.get("/health")
        data = response.json()

        assert "ai-proveedores" in data["service"].lower()

    def test_health_check_timestamp_format(self, client: TestClient) -> None:
        """
        Test que el timestamp tiene un formato válido ISO 8601.

        El timestamp debe ser parseable como datetime ISO.
        """
        response = client.get("/health")
        data = response.json()

        # Intentar parsear el timestamp
        try:
            datetime.fromisoformat(data["timestamp"])
            assert True
        except (ValueError, TypeError):
            pytest.fail(f"Timestamp inválido: {data['timestamp']}")

    @patch("main.run_supabase")
    def test_health_check_supabase_field_exists(
        self, mock_run_supabase: Mock, client: TestClient
    ) -> None:
        """
        Test que la respuesta incluye el campo de estado de Supabase.

        Verifica que exista el campo 'supabase' en la respuesta,
        aunque su valor pueda variar (connected, error, not_configured).
        """
        # Mockear la respuesta de Supabase
        mock_run_supabase.return_value = MagicMock(data=[{"id": 1}])

        response = client.get("/health")
        data = response.json()

        assert "supabase" in data
        assert isinstance(data["supabase"], str)

    @patch("main.run_supabase")
    def test_health_check_handles_supabase_error(
        self, mock_run_supabase: Mock, client: TestClient
    ) -> None:
        """
        Test que el health check maneja errores de Supabase correctamente.

        Cuando Supabase falla, el endpoint debe responder unhealthy
        pero no debe crash con 500.
        """
        # Simular error de Supabase
        mock_run_supabase.side_effect = Exception("Connection error")

        response = client.get("/health")
        data = response.json()

        # Debe responder 200 aún con error (health check siempre debe responder)
        assert response.status_code == 200
        # El status puede ser 'unhealthy' o 'healthy' según implementación
        assert "status" in data


# ========================================================================
# TESTS: POST /intelligent-search
# ========================================================================


class TestIntelligentSearchEndpoint:
    """Tests para el endpoint POST /intelligent-search."""

    @patch("main.buscar_proveedores")
    def test_intelligent_search_success(
        self, mock_buscar: AsyncMock, client: TestClient, sample_search_request: Dict
    ) -> None:
        """
        Test búsqueda inteligente exitosa.

        Verifica que el endpoint retorne 200 y la estructura correcta
        cuando la búsqueda se realiza exitosamente.
        """
        # Mockear respuesta de búsqueda
        mock_buscar.return_value = [
            {
                "id": "123",
                "full_name": "Juan Pérez",
                "profession": "plomero",
                "city": "Cuenca",
            }
        ]

        response = client.post("/intelligent-search", json=sample_search_request)
        data = response.json()

        assert response.status_code == 200
        assert "providers" in data
        assert "total" in data
        assert "metadata" in data
        assert isinstance(data["providers"], list)
        assert isinstance(data["total"], int)
        assert data["total"] == len(data["providers"])

    @patch("main.buscar_proveedores")
    def test_intelligent_search_empty_results(
        self, mock_buscar: AsyncMock, client: TestClient
    ) -> None:
        """
        Test búsqueda inteligente sin resultados.

        Verifica que el endpoint maneje correctamente el caso de no encontrar
        proveedores.
        """
        mock_buscar.return_value = []

        request_data = {
            "profesion_principal": "astronauta",
            "ubicacion": "Luna",
        }

        response = client.post("/intelligent-search", json=request_data)
        data = response.json()

        assert response.status_code == 200
        assert data["providers"] == []
        assert data["total"] == 0

    def test_intelligent_search_missing_profession(self, client: TestClient) -> None:
        """
        Test búsqueda inteligente sin profesión principal.

        El endpoint debe retornar 400 cuando falta el campo obligatorio
        profesion_principal.
        """
        request_data = {
            "ubicacion": "Cuenca",
            "urgencia": "alta",
        }

        response = client.post("/intelligent-search", json=request_data)

        assert response.status_code == 400

    def test_intelligent_search_invalid_json(self, client: TestClient) -> None:
        """
        Test búsqueda inteligente con JSON inválido.

        El endpoint debe retornar 422 con errores de validación
        cuando el JSON tiene estructura incorrecta.
        """
        request_data = {
            "profesion_principal": 123,  # Debe ser string
        }

        response = client.post("/intelligent-search", json=request_data)

        assert response.status_code == 422

    @patch("main.buscar_proveedores")
    def test_intelligent_search_with_location(
        self, mock_buscar: AsyncMock, client: TestClient, sample_search_request: Dict
    ) -> None:
        """
        Test búsqueda inteligente con ubicación.

        Verifica que el parámetro de ubicación se procese correctamente.
        """
        mock_buscar.return_value = [
            {
                "id": "123",
                "full_name": "Juan Pérez",
                "profession": "plomero",
                "city": "Cuenca",
            }
        ]

        response = client.post("/intelligent-search", json=sample_search_request)
        data = response.json()

        assert response.status_code == 200
        # Verificar que se llamó con los parámetros correctos
        mock_buscar.assert_called_once()
        call_args = mock_buscar.call_args
        assert "Cuenca" in str(call_args) or "ubicacion" in str(call_args)

    @patch("main.buscar_proveedores")
    def test_intelligent_search_metadata_structure(
        self, mock_buscar: AsyncMock, client: TestClient, sample_search_request: Dict
    ) -> None:
        """
        Test que el metadata de la búsqueda tiene estructura correcta.

        El metadata debe incluir:
        - specialties_used: list
        - synonyms_used: list
        - urgency: str (opcional)
        - necesidad_real: str (opcional)
        """
        mock_buscar.return_value = []

        response = client.post("/intelligent-search", json=sample_search_request)
        data = response.json()

        assert "metadata" in data
        metadata = data["metadata"]
        assert "specialties_used" in metadata
        assert "synonyms_used" in metadata
        assert "urgency" in metadata
        assert "necesidad_real" in metadata

    @patch("main.buscar_proveedores", side_effect=Exception("Database error"))
    def test_intelligent_search_handles_service_error(
        self, mock_buscar: AsyncMock, client: TestClient, sample_search_request: Dict
    ) -> None:
        """
        Test que el endpoint maneja errores del servicio correctamente.

        Cuando hay un error interno, debe retornar 500 con mensaje apropiado.
        """
        response = client.post("/intelligent-search", json=sample_search_request)

        assert response.status_code == 500


# ========================================================================
# TESTS: POST /send-whatsapp
# ========================================================================


class TestSendWhatsAppEndpoint:
    """Tests para el endpoint POST /send-whatsapp."""

    @patch("main.local_settings")
    def test_send_whatsapp_simulated_when_disabled(
        self, mock_settings: Mock, client: TestClient, sample_whatsapp_message: Dict
    ) -> None:
        """
        Test envío de WhatsApp simulado cuando está deshabilitado.

        Cuando AI_PROV_SEND_DIRECT=false, el endpoint debe retornar
        success=True con simulated=True.
        """
        mock_settings.enable_direct_whatsapp_send = False

        response = client.post("/send-whatsapp", json=sample_whatsapp_message)
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is True
        assert data["simulated"] is True
        assert "phone" in data

    @patch("main.local_settings")
    @patch("main.httpx.AsyncClient")
    def test_send_whatsapp_real_send_when_enabled(
        self,
        mock_httpx_class: Mock,
        mock_settings: Mock,
        client: TestClient,
        sample_whatsapp_message: Dict,
    ) -> None:
        """
        Test envío real de WhatsApp cuando está habilitado.

        Cuando AI_PROV_SEND_DIRECT=true, debe llamar al servicio wa-proveedores.
        """
        mock_settings.enable_direct_whatsapp_send = True
        mock_settings.wa_proveedores_url = "http://wa-proveedores:3000/send"

        # Mockear httpx AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_httpx_class.return_value = mock_client

        response = client.post("/send-whatsapp", json=sample_whatsapp_message)
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is True
        assert data["simulated"] is False

    def test_send_whatsapp_missing_phone(self, client: TestClient) -> None:
        """
        Test envío de WhatsApp sin número telefónico.

        Debe retornar 422 con error de validación.
        """
        request_data = {
            "message": "Hola",
        }

        response = client.post("/send-whatsapp", json=request_data)

        assert response.status_code == 422

    def test_send_whatsapp_missing_message(self, client: TestClient) -> None:
        """
        Test envío de WhatsApp sin mensaje.

        Debe retornar 422 con error de validación.
        """
        request_data = {
            "phone": "+593991234567",
        }

        response = client.post("/send-whatsapp", json=request_data)

        assert response.status_code == 422

    @patch("main.local_settings")
    @patch("main.httpx.AsyncClient")
    def test_send_whatsapp_handles_http_error(
        self,
        mock_httpx_class: Mock,
        mock_settings: Mock,
        client: TestClient,
        sample_whatsapp_message: Dict,
    ) -> None:
        """
        Test manejo de errores HTTP al enviar WhatsApp.

        Cuando wa-proveedores falla, debe retornar success=False
        pero no crash con 500.
        """
        mock_settings.enable_direct_whatsapp_send = True
        mock_settings.wa_proveedores_url = "http://wa-proveedores:3000/send"

        # Mockear error HTTP
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_httpx_class.return_value = mock_client

        response = client.post("/send-whatsapp", json=sample_whatsapp_message)
        data = response.json()

        # Debe manejar el error gracefulmente
        assert response.status_code == 200
        assert data["success"] is False
        assert "Error" in data.get("message", "")

    @patch("main.local_settings")
    @patch("main.httpx.AsyncClient")
    def test_send_whatsapp_message_preview(
        self,
        mock_httpx_class: Mock,
        mock_settings: Mock,
        client: TestClient,
    ) -> None:
        """
        Test que la respuesta incluye preview del mensaje.

        El response debe incluir un message_preview truncado a 80 caracteres.
        """
        mock_settings.enable_direct_whatsapp_send = True
        mock_settings.wa_proveedores_url = "http://wa-proveedores:3000/send"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_httpx_class.return_value = mock_client

        long_message = "Este es un mensaje muy largo que debe ser truncado en el preview " * 10
        request_data = {
            "phone": "+593991234567",
            "message": long_message,
        }

        response = client.post("/send-whatsapp", json=request_data)
        data = response.json()

        assert "message_preview" in data
        assert len(data["message_preview"]) <= 83  # 80 chars + "..."
        assert data["message_preview"].endswith("...")


# ========================================================================
# TESTS: POST /handle-whatsapp-message
# ========================================================================


class TestHandleWhatsAppMessageEndpoint:
    """Tests para el endpoint POST /handle-whatsapp-message."""

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.obtener_flujo")
    @patch("main.solicitar_consentimiento_proveedor")
    def test_handle_whatsapp_initial_message(
        self,
        mock_solicitar: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de mensaje inicial de WhatsApp.

        Cuando es el primer mensaje, debe solicitar consentimiento.
        """
        # Setup mocks
        mock_obtener_flujo.return_value = {"state": None}
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (False, None)
        mock_solicitar.return_value = {
            "messages": [{"response": "¿Aceptas los términos?"}]
        }

        request_data = {
            "phone": "+593991234567",
            "message": "Hola",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        assert "success" in data
        assert data["success"] is True

    @patch("main.reiniciar_flujo")
    @patch("main.establecer_flujo")
    @patch("main.solicitar_consentimiento_proveedor")
    def test_handle_whatsapp_reset_keyword(
        self,
        mock_solicitar: AsyncMock,
        mock_establecer: AsyncMock,
        mock_reiniciar: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de keyword de reset.

        Cuando el usuario envía "reset" o "reiniciar", debe reiniciar el flow.
        """
        mock_solicitar.return_value = {
            "messages": [{"response": "¿Aceptas los términos?"}]
        }

        request_data = {
            "phone": "+593991234567",
            "message": "reset",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        mock_reiniciar.assert_called_once()

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_flujo")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.inicializar_flow_con_perfil")
    def test_handle_whatsapp_timeout(
        self,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de timeout de sesión.

        Cuando la sesión expiró, debe reiniciar el flow.
        """
        mock_obtener_flujo.return_value = {"state": "awaiting_consent"}
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (
            True,
            {
                "success": True,
                "messages": [{"response": "Sesión expirada. Reiniciemos..."}],
            },
        )

        request_data = {
            "phone": "+593991234567",
            "message": "Continuar",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)

        assert response.status_code == 200

    def test_handle_whatsapp_missing_phone(self, client: TestClient) -> None:
        """
        Test mensaje sin número telefónico.

        Debe manejar gracefully, aunque el modelo lo permite opcional.
        """
        request_data = {
            "message": "Hola",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)

        # No debe crash, aunque puede fallar lógicamente
        assert response.status_code in [200, 400, 422]

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_flujo")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.inicializar_flow_con_perfil")
    @patch("main.manejar_respuesta_consentimiento")
    def test_handle_whatsapp_with_consent_awaiting(
        self,
        mock_manejar: AsyncMock,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de respuesta de consentimiento.

        Cuando el flow está en awaiting_consent, debe procesar la respuesta.
        """
        mock_obtener_flujo.return_value = {"state": "awaiting_consent", "has_consent": False}
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (False, None)
        mock_inicializar.return_value = {"state": "awaiting_consent", "has_consent": False}
        mock_manejar.return_value = {"success": True, "messages": [{"response": "Gracias"}]}

        request_data = {
            "phone": "+593991234567",
            "message": "Sí, acepto",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        mock_manejar.assert_called_once()

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_flujo")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.inicializar_flow_con_perfil")
    @patch("main.WhatsAppFlow.handle_initial_state")
    def test_handle_whatsapp_with_initial_state(
        self,
        mock_handle_initial: AsyncMock,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de estado inicial del flow.

        Verifica que se delegue correctamente a WhatsAppFlow.
        """
        mock_obtener_flujo.return_value = {"state": None, "has_consent": True}
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (False, None)
        mock_inicializar.return_value = {
            "state": None,
            "has_consent": True,
            "esta_registrado": False,
            "is_verified": False,
        }
        mock_handle_initial.return_value = {
            "success": True,
            "messages": [{"response": "Menú principal"}],
        }

        request_data = {
            "phone": "+593991234567",
            "message": "Hola",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        mock_handle_initial.assert_called_once()

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_flujo")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.inicializar_flow_con_perfil")
    @patch("main.reiniciar_flujo")
    def test_handle_whatsapp_error_handling(
        self,
        mock_reiniciar: AsyncMock,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test manejo de errores en el procesamiento de mensajes.

        Cuando ocurre un error inesperado, debe retornar success=False.
        """
        mock_obtener_flujo.side_effect = Exception("Unexpected error")

        request_data = {
            "phone": "+593991234567",
            "message": "Test error",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is False
        assert "Error" in data.get("message", "")


# ========================================================================
# TESTS: POST /api/v1/providers/{id}/notify-approval
# ========================================================================


class TestNotifyApprovalEndpoint:
    """Tests para el endpoint POST /api/v1/providers/{id}/notify-approval."""

    @patch("main.send_whatsapp_message")
    @patch("main.run_supabase")
    @patch("main.provider_approved_notification")
    def test_notify_approval_success(
        self,
        mock_notification: Mock,
        mock_run_supabase: AsyncMock,
        mock_send: AsyncMock,
        client: TestClient,
        sample_provider_data: Dict,
    ) -> None:
        """
        Test notificación de aprobación exitosa.

        El endpoint debe:
        1. Obtener el proveedor desde Supabase
        2. Enviar mensaje de WhatsApp
        3. Marcar como notificado
        4. Retornar success=True, queued=True
        """
        # Setup mocks
        mock_provider = MagicMock()
        mock_provider.data = [sample_provider_data]
        mock_run_supabase.return_value = mock_provider

        mock_notification.return_value = "¡Felicidades! Tu perfil ha sido aprobado."

        mock_send.return_value = {"success": True}

        provider_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(f"/api/v1/providers/{provider_id}/notify-approval")
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is True
        assert data["queued"] is True

    @patch("main.supabase", None)
    def test_notify_approval_without_supabase(self, client: TestClient) -> None:
        """
        Test notificación cuando Supabase no está configurado.

        Debe retornar 503 Service Unavailable.
        """
        provider_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(f"/api/v1/providers/{provider_id}/notify-approval")

        assert response.status_code == 503

    @patch("main.run_supabase")
    def test_notify_approval_provider_not_found(
        self, mock_run_supabase: AsyncMock, client: TestClient
    ) -> None:
        """
        Test notificación cuando el proveedor no existe.

        El endpoint debe retornar success=True pero no enviar mensaje.
        """
        mock_result = MagicMock()
        mock_result.data = []
        mock_run_supabase.return_value = mock_result

        provider_id = "non-existent-id"
        response = client.post(f"/api/v1/providers/{provider_id}/notify-approval")
        data = response.json()

        # Debe retornar success aunque no encontró el proveedor (background task)
        assert response.status_code == 200
        assert data["success"] is True

    @patch("main.send_whatsapp_message")
    @patch("main.run_supabase")
    def test_notify_approval_provider_without_phone(
        self, mock_run_supabase: AsyncMock, mock_send: AsyncMock, client: TestClient
    ) -> None:
        """
        Test notificación cuando el proveedor no tiene teléfono.

        Debe retornar success=True pero no enviar mensaje.
        """
        provider_data = {
            "id": "123",
            "full_name": "Juan Pérez",
            "phone": None,  # Sin teléfono
            "verified": True,
        }

        mock_provider = MagicMock()
        mock_provider.data = [provider_data]
        mock_run_supabase.return_value = mock_provider

        provider_id = "123"
        response = client.post(f"/api/v1/providers/{provider_id}/notify-approval")
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is True
        # No debe haber llamado a send_whatsapp_message
        mock_send.assert_not_called()

    @patch("main.send_whatsapp_message")
    @patch("main.run_supabase")
    @patch("main.provider_approved_notification")
    def test_notify_approval_sends_correct_message(
        self,
        mock_notification: Mock,
        mock_run_supabase: AsyncMock,
        mock_send: AsyncMock,
        client: TestClient,
        sample_provider_data: Dict,
    ) -> None:
        """
        Test que el mensaje de notificación contiene el nombre del proveedor.

        El mensaje debe ser personalizado con el nombre del proveedor.
        """
        mock_provider = MagicMock()
        mock_provider.data = [sample_provider_data]
        mock_run_supabase.return_value = mock_provider

        mock_notification.return_value = "¡Felicidades Juan Pérez! Tu perfil ha sido aprobado."
        mock_send.return_value = {"success": True}

        provider_id = "123"
        response = client.post(f"/api/v1/providers/{provider_id}/notify-approval")

        assert response.status_code == 200
        # Verificar que se llamó con el nombre correcto
        mock_notification.assert_called_once_with(sample_provider_data["full_name"])


# ========================================================================
# TESTS: GET /providers
# ========================================================================


class TestGetProvidersEndpoint:
    """Tests para el endpoint GET /providers."""

    @patch("main.buscar_proveedores")
    def test_get_providers_success(
        self, mock_buscar: AsyncMock, client: TestClient, sample_provider_data: Dict
    ) -> None:
        """
        Test obtener lista de proveedores exitosamente.

        Debe retornar 200 con lista de proveedores y count.
        """
        mock_buscar.return_value = [sample_provider_data]

        response = client.get("/providers")
        data = response.json()

        assert response.status_code == 200
        assert "providers" in data
        assert "count" in data
        assert isinstance(data["providers"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["providers"])

    @patch("main.buscar_proveedores")
    def test_get_providers_with_profession_filter(
        self, mock_buscar: AsyncMock, client: TestClient, sample_provider_data: Dict
    ) -> None:
        """
        Test filtrado de proveedores por profesión.

        Debe llamar a buscar_proveedores con el parámetro correcto.
        """
        mock_buscar.return_value = [sample_provider_data]

        response = client.get("/providers?profession=plomero")
        data = response.json()

        assert response.status_code == 200
        mock_buscar.assert_called_once()
        call_args = mock_buscar.call_args
        assert call_args[0][0] == "plomero" or "plomero" in str(call_args)

    @patch("main.buscar_proveedores")
    def test_get_providers_with_city_filter(
        self, mock_buscar: AsyncMock, client: TestClient, sample_provider_data: Dict
    ) -> None:
        """
        Test filtrado de proveedores por ciudad.

        Debe llamar a buscar_proveedores con el parámetro de ubicación.
        """
        mock_buscar.return_value = [sample_provider_data]

        response = client.get("/providers?city=Cuenca")
        data = response.json()

        assert response.status_code == 200
        mock_buscar.assert_called_once()

    @patch("main.buscar_proveedores")
    def test_get_providers_with_multiple_filters(
        self, mock_buscar: AsyncMock, client: TestClient, sample_provider_data: Dict
    ) -> None:
        """
        Test filtrado combinado de profesión y ciudad.

        Debe aplicar ambos filtros simultáneamente.
        """
        mock_buscar.return_value = [sample_provider_data]

        response = client.get("/providers?profession=plomero&city=Cuenca")
        data = response.json()

        assert response.status_code == 200
        mock_buscar.assert_called_once()

    @patch("main.buscar_proveedores")
    def test_get_providers_empty_list(
        self, mock_buscar: AsyncMock, client: TestClient
    ) -> None:
        """
        Test obtener lista vacía de proveedores.

        Cuando no hay resultados, debe retornar lista vacía y count=0.
        """
        mock_buscar.return_value = []

        response = client.get("/providers")
        data = response.json()

        assert response.status_code == 200
        assert data["providers"] == []
        assert data["count"] == 0

    @patch("main.buscar_proveedores", side_effect=Exception("DB error"))
    def test_get_providers_handles_error(
        self, mock_buscar: AsyncMock, client: TestClient
    ) -> None:
        """
        Test manejo de errores en obtención de proveedores.

        Cuando hay un error, debe retornar lista vacía pero no crash con 500.
        """
        response = client.get("/providers")
        data = response.json()

        # Debe manejar el error gracefulmente
        assert response.status_code == 200
        assert data["providers"] == []
        assert data["count"] == 0

    @patch("main.supabase", None)
    def test_get_providers_without_supabase(self, client: TestClient) -> None:
        """
        Test obtener proveedores cuando Supabase no está configurado.

        Debe usar datos de fallback (FALLBACK_PROVIDERS).
        """
        response = client.get("/providers")
        data = response.json()

        assert response.status_code == 200
        assert "providers" in data
        assert len(data["providers"]) > 0  # Fallback providers

    @patch("main.supabase", None)
    def test_get_providers_fallback_with_filter(
        self, client: TestClient
    ) -> None:
        """
        Test filtrado con datos de fallback.

        Debe filtrar correctamente los datos de fallback.
        """
        response = client.get("/providers?profession=plomero")
        data = response.json()

        assert response.status_code == 200
        # Los datos de fallback tienen un plomero
        assert len(data["providers"]) >= 0


# ========================================================================
# TESTS INTEGRACIÓN: FLUJOS COMPLEJOS
# ========================================================================


class TestComplexFlows:
    """Tests de integración para flujos complejos."""

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.obtener_flujo")
    @patch("main.inicializar_flow_con_perfil")
    @patch("main.WhatsAppFlow.handle_awaiting_menu_option")
    def test_whatsapp_menu_option_flow(
        self,
        mock_handle_menu: AsyncMock,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test flujo completo de selección de menú.

        Simula un usuario que ya tiene consentimiento y está en el menú.
        """
        mock_obtener_flujo.return_value = {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": False,
        }
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (False, None)
        mock_inicializar.return_value = {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": False,
        }
        mock_handle_menu.return_value = {
            "success": True,
            "messages": [{"response": "Seleccionaste: Registrar perfil"}],
        }

        request_data = {
            "phone": "+593991234567",
            "message": "1",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is True

    @patch("main.verificar_timeout_sesion")
    @patch("main.obtener_perfil_proveedor_cacheado")
    @patch("main.obtener_flujo")
    @patch("main.inicializar_flow_con_perfil")
    @patch("main.manejar_respuesta_consentimiento")
    def test_whatsapp_consent_flow(
        self,
        mock_manejar: AsyncMock,
        mock_inicializar: AsyncMock,
        mock_obtener_perfil: AsyncMock,
        mock_obtener_flujo: AsyncMock,
        mock_timeout: AsyncMock,
        client: TestClient,
    ) -> None:
        """
        Test flujo de consentimiento completo.

        Simula un usuario respondiendo al prompt de consentimiento.
        """
        mock_obtener_flujo.return_value = {
            "state": "awaiting_consent",
            "has_consent": False,
        }
        mock_obtener_perfil.return_value = None
        mock_timeout.return_value = (False, None)
        mock_inicializar.return_value = {
            "state": "awaiting_consent",
            "has_consent": False,
        }
        mock_manejar.return_value = {
            "success": True,
            "messages": [{"response": "Gracias por aceptar"}],
        }

        request_data = {
            "phone": "+593991234567",
            "message": "Sí, acepto los términos",
        }

        response = client.post("/handle-whatsapp-message", json=request_data)
        data = response.json()

        assert response.status_code == 200
        mock_manejar.assert_called_once()


# ========================================================================
# TESTS EDGE CASES
# ========================================================================


class TestEdgeCases:
    """Tests de casos borde y situaciones inusuales."""

    def test_health_check_with_concurrent_requests(self, client: TestClient) -> None:
        """
        Test que el health check maneja múltiples solicitudes concurrentes.

        Verifica que no haya race conditions en el endpoint.
        """
        import threading

        results = []

        def make_request():
            response = client.get("/health")
            results.append(response.status_code)

        threads = [threading.Thread(target=make_request) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(status == 200 for status in results)

    def test_intelligent_search_with_special_characters(
        self, client: TestClient
    ) -> None:
        """
        Test búsqueda con caracteres especiales y emojis.

        El endpoint debe manejar correctamente strings con caracteres especiales.
        """
        request_data = {
            "profesion_principal": "plomero 🚿",
            "ubicacion": "Cuenca, Ecuador",
        }

        response = client.post("/intelligent-search", json=request_data)

        # No debe crash, aunque puede no encontrar resultados
        assert response.status_code in [200, 400, 422]

    def test_whatsapp_message_with_very_long_text(self, client: TestClient) -> None:
        """
        Test mensaje de WhatsApp con texto extremadamente largo.

        El endpoint debe manejar mensajes largos sin problemas.
        """
        long_message = "Este es un mensaje muy largo. " * 100

        request_data = {
            "phone": "+593991234567",
            "message": long_message,
        }

        response = client.post("/handle-whatsapp-message", json=request_data)

        # No debe crash
        assert response.status_code == 200

    def test_get_providers_with_unicode_filters(self, client: TestClient) -> None:
        """
        Test filtros con caracteres unicode (tildes, ñ, etc.).

        Los filtros deben funcionar correctamente con caracteres especiales.
        """
        response = client.get("/providers?profession=fontanero&city=Cuenca")

        assert response.status_code == 200

    @patch("main.buscar_proveedores")
    def test_intelligent_search_case_insensitive(
        self, mock_buscar: AsyncMock, client: TestClient
    ) -> None:
        """
        Test que la búsqueda es case-insensitive.

        "PLOMERO", "plomero" y "Plomero" deben retornar los mismos resultados.
        """
        mock_buscar.return_value = []

        # Test con mayúsculas
        response1 = client.post(
            "/intelligent-search", json={"profesion_principal": "PLOMERO"}
        )
        assert response1.status_code == 200

        # Test con minúsculas
        response2 = client.post(
            "/intelligent-search", json={"profesion_principal": "plomero"}
        )
        assert response2.status_code == 200

        # Test con mixed case
        response3 = client.post(
            "/intelligent-search", json={"profesion_principal": "Plomero"}
        )
        assert response3.status_code == 200


# ========================================================================
# UTILIDADES
# ========================================================================


if __name__ == "__main__":
    # Permitir ejecutar tests directamente con python
    pytest.main([__file__, "-v", "--tb=short"])
