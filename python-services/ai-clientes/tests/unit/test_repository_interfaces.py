"""
Tests unitarios para verificar que los repositorios implementan correctamente las interfaces.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from repositories.interfaces import ICustomerRepository, IProviderRepository, IConsentRepository
    from services.customer.customer_repository import CustomerRepository
    from services.providers.provider_repository import ProviderRepository
    from services.consent.consent_repository import ConsentRepository
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestRepositoryInterfaces:
    """Verifica que los repositorios implementan las interfaces correctas."""

    def test_customer_repository_implements_interface(self):
        """CustomerRepository debe implementar ICustomerRepository."""
        # Verificar que es una subclase de la interfaz
        assert issubclass(CustomerRepository, ICustomerRepository)

        # Verificar que implementa todos los métodos requeridos
        required_methods = [
            'find_by_phone',
            'find_many',
            'update_customer_city',
            'clear_customer_city',
            'clear_customer_consent',
            'get_or_create_customer',
            'find_by_id',
            'create',
            'update',
            'delete',
        ]

        for method in required_methods:
            assert hasattr(CustomerRepository, method), f"Missing method: {method}"

    def test_provider_repository_implements_interface(self):
        """ProviderRepository debe implementar IProviderRepository."""
        assert issubclass(ProviderRepository, IProviderRepository)

        required_methods = [
            'search_by_city_and_profession',
            'search_by_city',
            'get_by_ids',
            'get_by_phone',
            'find_by_id',
            'create',
            'update',
            'delete',
        ]

        for method in required_methods:
            assert hasattr(ProviderRepository, method), f"Missing method: {method}"

    def test_consent_repository_implements_interface(self):
        """ConsentRepository debe implementar IConsentRepository."""
        assert issubclass(ConsentRepository, IConsentRepository)

        required_methods = [
            'update_customer_consent_status',
            'save_consent_record',
        ]

        for method in required_methods:
            assert hasattr(ConsentRepository, method), f"Missing method: {method}"
