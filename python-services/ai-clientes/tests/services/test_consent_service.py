"""
Tests unitarios para ConsentService.

Este módulo prueba la funcionalidad del servicio de consentimiento
de clientes para AI Clientes.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime

from services.consent_service import ConsentService


@pytest.fixture
def mock_supabase():
    """Fixture que mockea el cliente de Supabase."""
    supabase = MagicMock()
    supabase.table = MagicMock()

    # Mock para la tabla customers
    mock_customers_table = MagicMock()
    mock_customers_table.update = MagicMock(return_value=mock_customers_table)
    mock_customers_table.eq = MagicMock(return_value=mock_customers_table)
    mock_customers_table.execute = AsyncMock()

    # Mock para la tabla consents
    mock_consents_table = MagicMock()
    mock_consents_table.insert = MagicMock(return_value=mock_consents_table)
    mock_consents_table.execute = AsyncMock()

    def table_mock(table_name):
        if table_name == "customers":
            return mock_customers_table
        elif table_name == "consents":
            return mock_consents_table
        return MagicMock()

    supabase.table = table_mock
    return supabase


@pytest.fixture
def consent_service(mock_supabase):
    """Fixture que instancia el ConsentService con Supabase mockeado."""
    return ConsentService(supabase_client=mock_supabase)


@pytest.fixture
def customer_profile():
    """Fixture que proporciona un perfil de cliente de prueba."""
    return {
        "id": "customer-123",
        "phone": "+593987654321",
        "has_consent": False,
        "city": "Quito",
    }


@pytest.fixture
def sample_payload():
    """Fixture que proporciona un payload de WhatsApp de prueba."""
    return {
        "from_number": "+593987654321",
        "content": "1",
        "selected_option": "1",
        "message_id": "msg-123",
        "timestamp": datetime.utcnow().isoformat(),
        "message_type": "text",
        "device_type": "mobile",
    }


class TestConsentServiceNormalizarBoton:
    """Tests para el método normalize_button."""

    def test_normalize_button_numeric_option(self, consent_service):
        """Verifica que normaliza correctamente opciones numéricas."""
        assert consent_service.normalize_button("1") == "1"
        assert consent_service.normalize_button("2") == "2"
        assert consent_service.normalize_button("10") == "10"

    def test_normalize_button_with_text(self, consent_service):
        """Verifica que extrae el número de textos con formato '1 Texto'."""
        assert consent_service.normalize_button("1 Sí, acepto") == "1"
        assert consent_service.normalize_button("2 No acepto") == "2"
        assert consent_service.normalize_button("3 Opción tres") == "3"

    def test_normalize_button_removes_extra_spaces(self, consent_service):
        """Verifica que elimina espacios múltiples."""
        assert consent_service.normalize_button("1  Sí,    acepto") == "1"

    def test_normalize_button_none_input(self, consent_service):
        """Verifica que maneja correctamente entrada None."""
        assert consent_service.normalize_button(None) is None

    def test_normalize_button_empty_string(self, consent_service):
        """Verifica que maneja correctamente cadena vacía."""
        assert consent_service.normalize_button("") is None
        assert consent_service.normalize_button("   ") is None

    def test_normalize_button_text_only(self, consent_service):
        """Verifica que devuelve el texto si no hay número al inicio."""
        assert consent_service.normalize_button("Acepto") == "Acepto"
        assert consent_service.normalize_button("No acepto") == "No acepto"


class TestConsentServiceRequestConsent:
    """Tests para el método request_consent."""

    @pytest.mark.asyncio
    async def test_request_consent_returns_messages(self, consent_service):
        """Verifica que request_consent devuelve mensajes de solicitud."""
        result = await consent_service.request_consent("+593987654321")

        assert "messages" in result
        assert isinstance(result["messages"], list)
        assert len(result["messages"]) > 0
        assert all("response" in msg for msg in result["messages"])


class TestConsentServiceHandleConsentResponse:
    """Tests para el método handle_consent_response."""

    @pytest.mark.asyncio
    async def test_handle_consent_accepted(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Verifica que procesa correctamente la aceptación de consentimiento."""
        # Configurar mocks
        mensaje_inicial = "Mensaje inicial de servicio"

        result = await consent_service.handle_consent_response(
            phone="+593987654321",
            customer_profile=customer_profile,
            selected_option="1",
            payload=sample_payload,
            mensaje_inicial_servicio=mensaje_inicial,
        )

        # Verificar que se actualizó el consentimiento en customers
        customers_table = mock_supabase.table("customers")
        customers_table.update.assert_called_once_with({"has_consent": True})
        customers_table.eq.assert_called_once_with("id", "customer-123")

        # Verificar que se insertó el registro en consents
        consents_table = mock_supabase.table("consents")
        consents_table.insert.assert_called_once()
        call_args = consents_table.insert.call_args[0][0]
        assert call_args["user_id"] == "customer-123"
        assert call_args["user_type"] == "customer"
        assert call_args["response"] == "accepted"

        # Verificar la respuesta
        assert "response" in result
        assert result["response"] == mensaje_inicial

    @pytest.mark.asyncio
    async def test_handle_consent_declined(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Verifica que procesa correctamente el rechazo de consentimiento."""
        result = await consent_service.handle_consent_response(
            phone="+593987654321",
            customer_profile=customer_profile,
            selected_option="2",
            payload=sample_payload,
            mensaje_inicial_servicio="Mensaje inicial",
        )

        # Verificar que NO se actualizó customers (no hay update para has_consent=False)
        # Verificar que se insertó el registro en consents
        consents_table = mock_supabase.table("consents")
        consents_table.insert.assert_called_once()
        call_args = consents_table.insert.call_args[0][0]
        assert call_args["response"] == "declined"

        # Verificar la respuesta
        assert "response" in result
        assert "Sin tu consentimiento" in result["response"]


class TestConsentServiceValidateAndHandleConsent:
    """Tests para el método validate_and_handle_consent."""

    @pytest.mark.asyncio
    async def test_validate_consent_with_existing_consent(
        self, consent_service, customer_profile
    ):
        """Verifica que devuelve None si el cliente ya tiene consentimiento."""
        customer_profile["has_consent"] = True

        result = await consent_service.validate_and_handle_consent(
            phone="+593987654321",
            customer_profile=customer_profile,
            payload={},
            mensaje_inicial_servicio="Mensaje inicial",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_consent_without_profile_requests_consent(
        self, consent_service
    ):
        """Verifica que solicita consentimiento si no hay perfil."""
        result = await consent_service.validate_and_handle_consent(
            phone="+593987654321",
            customer_profile=None,
            payload={},
            mensaje_inicial_servicio="Mensaje inicial",
        )

        assert result is not None
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_validate_consent_with_numeric_response(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Verifica que procesa respuesta numérica '1' como aceptación."""
        result = await consent_service.validate_and_handle_consent(
            phone="+593987654321",
            customer_profile=customer_profile,
            payload=sample_payload,
            mensaje_inicial_servicio="Mensaje inicial",
        )

        assert result is not None
        assert "response" in result

    @pytest.mark.asyncio
    async def test_validate_consent_with_button_response(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Verifica que procesa respuesta de botón 'Acepto'."""
        payload = sample_payload.copy()
        payload["selected_option"] = "Acepto"
        payload["content"] = ""

        result = await consent_service.validate_and_handle_consent(
            phone="+593987654321",
            customer_profile=customer_profile,
            payload=payload,
            mensaje_inicial_servicio="Mensaje inicial",
        )

        # Debe solicitar consentimiento nuevamente porque "Acepto" no está
        # en las opciones numéricas directamente
        assert result is not None

    @pytest.mark.asyncio
    async def test_validate_consent_with_decline_response(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Verifica que procesa respuesta '2' como rechazo."""
        payload = sample_payload.copy()
        payload["selected_option"] = "2"
        payload["content"] = "2"

        result = await consent_service.validate_and_handle_consent(
            phone="+593987654321",
            customer_profile=customer_profile,
            payload=payload,
            mensaje_inicial_servicio="Mensaje inicial",
        )

        assert result is not None
        assert "response" in result


class TestConsentServiceIntegration:
    """Tests de integración para ConsentService."""

    @pytest.mark.asyncio
    async def test_full_consent_flow_accepted(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Prueba el flujo completo de aceptación de consentimiento."""
        phone = "+593987654321"
        mensaje_inicial = "¿En qué podemos ayudarte?"

        # Paso 1: Solicitar consentimiento
        request = await consent_service.request_consent(phone)
        assert "messages" in request

        # Paso 2: Procesar aceptación
        customer_profile["has_consent"] = False
        response = await consent_service.handle_consent_response(
            phone=phone,
            customer_profile=customer_profile,
            selected_option="1",
            payload=sample_payload,
            mensaje_inicial_servicio=mensaje_inicial,
        )

        assert response["response"] == mensaje_inicial

        # Verificar que se actualizó en Supabase
        customers_table = mock_supabase.table("customers")
        assert customers_table.update.called
        assert customers_table.eq.called

    @pytest.mark.asyncio
    async def test_full_consent_flow_declined(
        self, consent_service, customer_profile, sample_payload, mock_supabase
    ):
        """Prueba el flujo completo de rechazo de consentimiento."""
        phone = "+593987654321"

        # Paso 1: Solicitar consentimiento
        request = await consent_service.request_consent(phone)
        assert "messages" in request

        # Paso 2: Procesar rechazo
        response = await consent_service.handle_consent_response(
            phone=phone,
            customer_profile=customer_profile,
            selected_option="2",
            payload=sample_payload,
            mensaje_inicial_servicio="Mensaje inicial",
        )

        assert "Sin tu consentimiento" in response["response"]

        # Verificar que se registró el rechazo
        consents_table = mock_supabase.table("consents")
        assert consents_table.insert.called
