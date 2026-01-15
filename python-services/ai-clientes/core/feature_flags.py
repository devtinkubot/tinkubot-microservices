"""
Feature Flags para migración gradual a nueva arquitectura en ai-clientes.

Este módulo centraliza todos los feature flags que controlan la activación
gradual de las nuevas funcionalidades implementadas en el plan arquitectónico.

IMPORTANTE: Los flags deben activarse en orden secuencial (Fase 1 → Fase 2 → Fase 5)
y solo después de verificar que los tests pasan exitosamente.

Author: Claude Sonnet 4.5
Created: 2025-01-14
Updated: 2026-01-15 - Now reads from environment variables
"""

import os

# =============================================================================
# FEATURE FLAGS - MIGRACIÓN GRADUAL AI-CLIENTES
# =============================================================================

# FASE 1: Repository Pattern + Interfaces
# Activa el uso de interfaces en repositorios (ya implementado).
# - Implementa: Interfaces ICustomerRepository, IProviderRepository, IConsentRepository
# - Archivos: core/interfaces.py, repositories/interfaces.py
# - Tests: tests/unit/test_repository_interfaces.py
# ESTADO: ✅ ACTIVO (interfaces están implementadas)
USE_REPOSITORY_INTERFACES = True

# FASE 2: State Machine
# Activa la máquina de estados para validación de transiciones de conversación.
# - Implementa: State Machine + Strategy Pattern
# - Archivos: core/state_machine.py, services/conversation_orchestrator.py
# - Tests: tests/unit/test_state_machine.py
# ESTADO: ✅ ACTIVO (validación de transiciones habilitada)
USE_STATE_MACHINE = True  # ACTIVADO: Validación de transiciones habilitada

# FASE 3: Saga Pattern
# Activa el patrón Saga para rollback automático en caso de errores.
# - Implementa: Saga + Command Pattern
# - Archivos: core/saga.py, core/commands.py, services/conversation_orchestrator.py
# - Tests: tests/unit/test_saga.py
# ESTADO: ✅ ACTIVO (rollback transaccional habilitado)
USE_SAGA_ROLLBACK = True  # ACTIVADO: Rollback automático habilitado

# FASE 4: Performance Optimizations
# Activa optimizaciones de performance y cacheo.
# - Implementa: Cache layer + Performance metrics
# - Archivos: core/cache.py, core/metrics.py, servicios optimizados
# - Tests: tests/unit/test_cache.py, tests/unit/test_metrics.py
# ESTADO: ✅ ACTIVO (optimizaciones habilitadas)
ENABLE_PERFORMANCE_OPTIMIZATIONS = True  # ACTIVADO: Optimizaciones habilitadas

# FASE 5: Feature Flags System
# Activa este sistema de feature flags y el endpoint de debug.
# ESTADO: ✅ ACTIVO (este archivo ya existe)
ENABLE_FEATURE_FLAGS = True

# FASE 6: Enhanced Search (Mejoras Inmediatas)
# Activa las mejoras inmediatas al sistema de búsqueda.
# - Implementa: IntentClassifier, QueryExpander, SynonymLearner
# - Archivos: services/intent_classifier.py, services/query_expansion.py, services/synonym_learner.py
# - Objetivo: 40% reducción en falsos negativos + aprendizaje continuo
# - Timeline: 3 semanas
# - ENFOQUE: Búsqueda funcional pura (sin fallbacks)
# ESTADO: ✅ ACTIVO - Leer desde environment variables
USE_INTENT_CLASSIFICATION = os.getenv("USE_INTENT_CLASSIFICATION", "false") == "true"
USE_QUERY_EXPANSION = os.getenv("USE_QUERY_EXPANSION", "false") == "true"
USE_SYNONYM_LEARNING = os.getenv("USE_SYNONYM_LEARNING", "false") == "true"

# FASE 7: Auto-Generated Synonyms (Proactivo)
# Activa la generación automática de sinónimos cuando se aprueba un proveedor.
# - Implementa: ProviderSynonymOptimizer, AutoProfessionGenerator
# - Archivos: services/provider_synonym_optimizer.py, services/auto_profession_generator.py
# - Objetivo: Sinónimos preparados ANTES de que alguien busque
# - Trigger: Evento MQTT providers/approved
# - ESTADO: ⏸️ INACTIVO por defecto (requiere activación manual)
USE_AUTO_SYNONYM_GENERATION = os.getenv("USE_AUTO_SYNONYM_GENERATION", "false") == "true"


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
        'USE_REPOSITORY_INTERFACES': USE_REPOSITORY_INTERFACES,
        'USE_STATE_MACHINE': USE_STATE_MACHINE,
        'USE_SAGA_ROLLBACK': USE_SAGA_ROLLBACK,
        'ENABLE_PERFORMANCE_OPTIMIZATIONS': ENABLE_PERFORMANCE_OPTIMIZATIONS,
        'ENABLE_FEATURE_FLAGS': ENABLE_FEATURE_FLAGS,
        'USE_INTENT_CLASSIFICATION': USE_INTENT_CLASSIFICATION,
        'USE_QUERY_EXPANSION': USE_QUERY_EXPANSION,
        'USE_SYNONYM_LEARNING': USE_SYNONYM_LEARNING,
        'USE_AUTO_SYNONYM_GENERATION': USE_AUTO_SYNONYM_GENERATION,
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
        1: USE_REPOSITORY_INTERFACES,
        2: USE_REPOSITORY_INTERFACES and USE_STATE_MACHINE,
        3: (USE_REPOSITORY_INTERFACES and USE_STATE_MACHINE and
            USE_SAGA_ROLLBACK),
        4: (USE_REPOSITORY_INTERFACES and USE_STATE_MACHINE and
            USE_SAGA_ROLLBACK and ENABLE_PERFORMANCE_OPTIMIZATIONS),
        5: (USE_REPOSITORY_INTERFACES and USE_STATE_MACHINE and
            USE_SAGA_ROLLBACK and ENABLE_PERFORMANCE_OPTIMIZATIONS and
            ENABLE_FEATURE_FLAGS),
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
    if USE_STATE_MACHINE and not USE_REPOSITORY_INTERFACES:
        errors.append("STATE_MACHINE requiere REPOSITORY_INTERFACES activado primero")

    if USE_SAGA_ROLLBACK and not USE_STATE_MACHINE:
        errors.append("SAGA_ROLLBACK requiere STATE_MACHINE activado primero")

    if ENABLE_PERFORMANCE_OPTIMIZATIONS and not USE_SAGA_ROLLBACK:
        errors.append("PERFORMANCE_OPTIMIZATIONS requiere SAGA_ROLLBACK activado primero")

    if ENABLE_FEATURE_FLAGS:
        if not (USE_REPOSITORY_INTERFACES):
            errors.append("FEATURE_FLAGS requiere REPOSITORY_INTERFACES activado")

    # Advertencias de fases incompletas
    if USE_REPOSITORY_INTERFACES and not USE_STATE_MACHINE:
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
    print("ESTADO ACTUAL DE FEATURE FLAGS - MIGRACIÓN ARQUITECTÓNICA AI-CLIENTES")
    print("="*70)

    flags = get_all_flags()
    validation = validate_activation_order()

    print("\n📊 ESTADO DE FLAGS:\n")
    for flag_name, flag_value in flags.items():
        status = "✅ ACTIVO" if flag_value else "❌ INACTIVO"
        print(f"  {flag_name:35} : {status}")

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
