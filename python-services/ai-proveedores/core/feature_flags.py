"""
Feature Flags para migración gradual a nueva arquitectura.

Este módulo centraliza todos los feature flags que controlan la activación
gradual de las nuevas funcionalidades implementadas en el plan arquitectónico.

IMPORTANTE: Los flags deben activarse en orden secuencial (Fase 1 → Fase 5)
y solo después de verificar que los tests pasan exitosamente.

Author: Claude Sonnet 4.5
Created: 2025-01-13
"""

# =============================================================================
# FEATURE FLAGS - MIGRACIÓN GRADUAL
# =============================================================================

# FASE 1: Repository Pattern
# Activa el uso del patrón Repository en lugar del acceso directo a la base de datos.
# - Implementa: Repository + Command Pattern
# - Archivos: core/repositories/, flows/provider_flow.py
# - Tests: tests/unit/repositories/, tests/integration/test_repository_pattern.py
# ESTADO: ✅ ACTIVO
USE_REPOSITORY_PATTERN = True

# FASE 2: State Machine
# Activa la máquina de estados para validación de proveedores.
# - Implementa: State Machine + Strategy Pattern
# - Archivos: core/state_machine/, services/validation_service.py
# - Tests: tests/unit/state_machine/, tests/integration/test_state_machine_integration.py
# ESTADO: ✅ ACTIVO
USE_STATE_MACHINE = True

# FASE 3: Saga Pattern
# Activa el patrón Saga para rollback automático en caso de errores.
# - Implementa: Saga + Compensation Actions
# - Archivos: core/saga/, flows/provider_flow.py
# - Tests: tests/unit/saga/, tests/integration/test_saga_integration.py
# ESTADO: ✅ ACTIVO
USE_SAGA_ROLLBACK = True

# FASE 4: Validación de Imágenes
# Activa la validación optimizada de imágenes y carga en paralelo.
# - Implementa: Validación por lotes + Parallel uploads
# - Archivos: services/validation_service.py, services/upload_service.py
# - Tests: tests/integration/test_image_validation_parallel.py
# ESTADO: ✅ ACTIVO
ENABLE_IMAGE_VALIDATION = True
ENABLE_PARALLEL_UPLOAD = True

# FASE 5: Limpieza de Código Legacy
# Una vez activadas todas las fases anteriores, permite eliminar código obsoleto.
# - Elimina: Código deprecado, comentarios temporales, funciones duplicadas
# - Archivos: Todos los archivos modificados en fases anteriores
# - Tests: Regression tests completos
# ESTADO: ✅ ACTIVO
ENABLE_LEGACY_CLEANUP = True


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def get_all_flags() -> dict:
    """
    Retorna el estado actual de todos los feature flags.

    Returns:
        dict: Diccionario con nombre y estado de cada flag
    """
    return {
        'USE_REPOSITORY_PATTERN': USE_REPOSITORY_PATTERN,
        'USE_STATE_MACHINE': USE_STATE_MACHINE,
        'USE_SAGA_ROLLBACK': USE_SAGA_ROLLBACK,
        'ENABLE_IMAGE_VALIDATION': ENABLE_IMAGE_VALIDATION,
        'ENABLE_PARALLEL_UPLOAD': ENABLE_PARALLEL_UPLOAD,
        'ENABLE_LEGACY_CLEANUP': ENABLE_LEGACY_CLEANUP,
    }


def get_phase_status(phase: int) -> bool:
    """
    Verifica si una fase específica está completamente activada.

    Args:
        phase: Número de fase (1-5)

    Returns:
        bool: True si la fase está activada, False en caso contrario

    Raises:
        ValueError: Si el número de fase es inválido
    """
    phase_requirements = {
        1: USE_REPOSITORY_PATTERN,
        2: USE_REPOSITORY_PATTERN and USE_STATE_MACHINE,
        3: USE_REPOSITORY_PATTERN and USE_STATE_MACHINE and USE_SAGA_ROLLBACK,
        4: (USE_REPOSITORY_PATTERN and USE_STATE_MACHINE and
            USE_SAGA_ROLLBACK and ENABLE_IMAGE_VALIDATION and
            ENABLE_PARALLEL_UPLOAD),
        5: (USE_REPOSITORY_PATTERN and USE_STATE_MACHINE and
            USE_SAGA_ROLLBACK and ENABLE_IMAGE_VALIDATION and
            ENABLE_PARALLEL_UPLOAD and ENABLE_LEGACY_CLEANUP),
    }

    if phase not in phase_requirements:
        raise ValueError(f"Fase inválida: {phase}. Debe ser 1-5")

    return phase_requirements[phase]


def validate_activation_order() -> dict:
    """
    Valida que los flags estén activados en el orden correcto.

    Returns:
        dict: Resultado de la validación con:
            - valid (bool): True si el orden es correcto
            - errors (list): Lista de mensajes de error
            - warnings (list): Lista de advertencias
    """
    flags = get_all_flags()
    errors = []
    warnings = []

    # Validar orden de activación
    if USE_STATE_MACHINE and not USE_REPOSITORY_PATTERN:
        errors.append("STATE_MACHINE requiere REPOSITORY_PATTERN activado primero")

    if USE_SAGA_ROLLBACK and not USE_STATE_MACHINE:
        errors.append("SAGA_ROLLBACK requiere STATE_MACHINE activado primero")

    if ENABLE_IMAGE_VALIDATION and not USE_SAGA_ROLLBACK:
        errors.append("IMAGE_VALIDATION requiere SAGA_ROLLBACK activado primero")

    if ENABLE_PARALLEL_UPLOAD and not ENABLE_IMAGE_VALIDATION:
        errors.append("PARALLEL_UPLOAD requiere IMAGE_VALIDATION activado primero")

    if ENABLE_LEGACY_CLEANUP:
        if not (USE_REPOSITORY_PATTERN and USE_STATE_MACHINE and
                USE_SAGA_ROLLBACK and ENABLE_IMAGE_VALIDATION and
                ENABLE_PARALLEL_UPLOAD):
            errors.append("LEGACY_CLEANUP requiere todas las fases anteriores activadas")

    # Advertencias de fases incompletas
    if USE_REPOSITORY_PATTERN and not USE_STATE_MACHINE:
        warnings.append("Fase 1 activa pero Fase 2 no - considerar activar STATE_MACHINE")

    if USE_STATE_MACHINE and not USE_SAGA_ROLLBACK:
        warnings.append("Fase 2 activa pero Fase 3 no - considerar activar SAGA_ROLLBACK")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'current_flags': flags
    }


def print_status():
    """
    Imprime el estado actual de todos los feature flags en formato legible.
    """
    print("\n" + "="*70)
    print("ESTADO ACTUAL DE FEATURE FLAGS - MIGRACIÓN ARQUITECTÓNICA")
    print("="*70)

    flags = get_all_flags()
    validation = validate_activation_order()

    print("\n📊 ESTADO DE FLAGS:\n")
    for flag_name, flag_value in flags.items():
        status = "✅ ACTIVO" if flag_value else "❌ INACTIVO"
        print(f"  {flag_name:30} : {status}")

    print("\n" + "-"*70)
    print("VALIDACIÓN DE ORDEN DE ACTIVACIÓN:")
    print("-"*70)

    if validation['valid']:
        print("  ✅ Orden de activación CORRECTO")
    else:
        print("  ❌ Orden de activación INCORRECTO")
        print("\n  Errores encontrados:")
        for error in validation['errors']:
            print(f"    • {error}")

    if validation['warnings']:
        print("\n  ⚠️  Advertencias:")
        for warning in validation['warnings']:
            print(f"    • {warning}")

    print("\n" + "-"*70)
    print("ESTADO DE FASES:")
    print("-"*70)

    for phase_num in range(1, 6):
        is_active = get_phase_status(phase_num)
        status = "✅ COMPLETADA" if is_active else "⏳ PENDIENTE"
        print(f"  Fase {phase_num}: {status}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    # Ejecutar diagnóstico de flags
    print_status()
