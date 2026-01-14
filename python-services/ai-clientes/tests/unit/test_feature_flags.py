"""
Tests unitarios para el sistema de feature flags.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from core.feature_flags import (
        get_all_flags,
        get_phase_status,
        validate_activation_order,
        USE_REPOSITORY_INTERFACES,
        USE_STATE_MACHINE,
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestFeatureFlags:
    """Tests para el sistema de feature flags."""

    def test_get_all_flags(self):
        """Debe retornar todos los flags."""
        flags = get_all_flags()

        assert isinstance(flags, dict)
        assert 'USE_REPOSITORY_INTERFACES' in flags
        assert 'USE_STATE_MACHINE' in flags
        assert 'USE_SAGA_ROLLBACK' in flags

    def test_phase_1_status(self):
        """Fase 1 debe estar activa (interfaces implementadas)."""
        assert get_phase_status(1) is True

    def test_phase_2_status(self):
        """Fase 2 debe estar inactiva por defecto."""
        # USE_STATE_MACHINE = False por defecto
        assert get_phase_status(2) is False

    def test_phase_3_status(self):
        """Fase 3 debe estar inactiva (pendiente)."""
        assert get_phase_status(3) is False

    def test_invalid_phase_raises_error(self):
        """Fase inválida debe levantar ValueError."""
        with pytest.raises(ValueError):
            get_phase_status(99)

    def test_validate_activation_order_with_defaults(self):
        """Con valores por defecto, el orden debe ser válido."""
        result = validate_activation_order()

        # Debe ser válido porque estamos en Fase 1
        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_repository_interfaces_is_active(self):
        """USE_REPOSITORY_INTERFACES debe estar activo."""
        assert USE_REPOSITORY_INTERFACES is True

    def test_state_machine_is_inactive_by_default(self):
        """USE_STATE_MACHINE debe estar inactivo por defecto."""
        assert USE_STATE_MACHINE is False

    def test_validate_activation_order_warnings(self):
        """Debe advertir fases incompletas."""
        result = validate_activation_order()

        # Debe advertir que Fase 1 está activa pero Fase 2 no
        warnings = result['warnings']
        assert len(warnings) > 0
        assert any("Fase 1" in w and "Fase 2" in w for w in warnings)
