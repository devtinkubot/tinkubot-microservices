"""
Test Script - Enhanced Search V2 (Mejoras Inmediatas)

Este script valida la implementación de las mejoras de búsqueda:
1. IntentClassifier
2. QueryExpander
3. Smart Fallback
4. Integración completa V2

Ejecutar con:
    PYTHONPATH=/home/du/produccion/tinkubot-microservices:/home/du/produccion/tinkubot-microservices/python-services:/home/du/produccion/tinkubot-microservices/python-services/shared-lib python3 tests/integration/test_search_v2.py
"""

import asyncio
import logging
import sys
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# SETUP
# ============================================================================

async def setup_test_environment():
    """Inicializa el entorno de testing."""
    logger.info("🔧 Configurando entorno de testing...")

    # Importar servicios
    try:
        from services.intent_classifier import get_intent_classifier
        from services.query_expansion import get_query_expander
        from services.dynamic_service_catalog import dynamic_service_catalog
        from core.feature_flags import (
            USE_INTENT_CLASSIFICATION,
            USE_QUERY_EXPANSION
        )

        logger.info("✅ Servicios importados correctamente")
        logger.info(f"   USE_INTENT_CLASSIFICATION: {USE_INTENT_CLASSIFICATION}")
        logger.info(f"   USE_QUERY_EXPANSION: {USE_QUERY_EXPANSION}")

        return {
            "intent_classifier": get_intent_classifier(),
            "query_expander": get_query_expander(),
            "dynamic_catalog": dynamic_service_catalog
        }

    except ImportError as e:
        logger.error(f"❌ Error importando servicios: {e}")
        return None


# ============================================================================
# TEST 1: IntentClassifier
# ============================================================================

async def test_intent_classifier(services):
    """Test 1: Clasificación de intenciones."""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: IntentClassifier")
    logger.info("="*70)

    classifier = services["intent_classifier"]

    test_queries = [
        ("necesito un plomero en Quito", "direct"),
        ("tengo goteras en el techo", "need_based"),
        ("limpieza facial", "direct"),
        ("cortocircuito en la casa", "need_based"),
        ("ayuda", "ambiguous"),
    ]

    passed = 0
    failed = 0

    for query, expected_intent in test_queries:
        result = classifier.classify_intent(query)
        result_value = result.value if hasattr(result, 'value') else result

        status = "✅" if result_value == expected_intent else "❌"
        logger.info(f"{status} Query: '{query}'")
        logger.info(f"   Expected: {expected_intent}, Got: {result_value}")

        if result_value == expected_intent:
            passed += 1
        else:
            failed += 1

        # Test infer profession
        if expected_intent == "need_based":
            inferred = classifier.infer_profession_from_need(query)
            logger.info(f"   Inferred profession: {inferred}")

    logger.info(f"\n📊 Resultados: {passed} passed, {failed} failed")
    return failed == 0


# ============================================================================
# TEST 2: QueryExpander
# ============================================================================

async def test_query_expander(services):
    """Test 2: Expansión de queries."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: QueryExpander")
    logger.info("="*70)

    expander = services["query_expander"]

    if not expander:
        logger.warning("⚠️ QueryExpander no está inicializado (saltando test)")
        return True

    test_queries = [
        ("tengo goteras", "plomero"),
        ("limpieza facial", "esteticista"),
        ("cortocircuito", "electricista"),
    ]

    passed = 0
    failed = 0

    for query, expected_profession in test_queries:
        try:
            result = await expander.expand_query(
                query=query,
                use_ai=False,  # Usar solo estáticos para testing
                semaphore=None
            )

            expanded_terms = result.get("expanded_terms", [])
            inferred = result.get("inferred_profession")
            method = result.get("expansion_method")

            # Verificar que se expandió
            has_expansion = len(expanded_terms) > 1
            has_profession = inferred == expected_profession

            status = "✅" if (has_expansion and has_profession) else "❌"
            logger.info(f"{status} Query: '{query}'")
            logger.info(f"   Expanded terms: {expanded_terms[:3]}... ({len(expanded_terms)} total)")
            logger.info(f"   Inferred profession: {inferred}")
            logger.info(f"   Method: {method}")

            if has_expansion and has_profession:
                passed += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"❌ Error expandiendo query '{query}': {e}")
            failed += 1

    logger.info(f"\n📊 Resultados: {passed} passed, {failed} failed")
    return failed == 0


# ============================================================================
# TEST 3: DynamicServiceCatalog
# ============================================================================

async def test_dynamic_catalog(services):
    """Test 3: Catálogo dinámico de servicios."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: DynamicServiceCatalog")
    logger.info("="*70)

    catalog = services["dynamic_catalog"]

    if not catalog:
        logger.warning("⚠️ DynamicServiceCatalog no está inicializado (saltando test)")
        return True

    # Cargar catálogo
    synonyms_dict = await catalog.get_synonyms()

    logger.info(f"📚 Catálogo cargado: {len(synonyms_dict)} profesiones")

    # Mostrar top profesiones
    top_professions = sorted(
        synonyms_dict.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:5]

    logger.info("\n🔝 Top 5 profesiones por sinónimos:")
    for profession, synonyms in top_professions:
        logger.info(f"   {profession}: {len(synonyms)} sinónimos")

    # Test búsqueda
    test_searches = [
        ("community manager", "marketing"),
        ("gestor de redes sociales", "marketing"),
        ("goteras", "plomero"),
    ]

    passed = 0
    failed = 0

    for search_term, expected in test_searches:
        result = await catalog.find_profession(search_term)
        status = "✅" if result == expected else "❌"
        logger.info(f"{status} Search: '{search_term}' → {result} (expected: {expected})")

        if result == expected:
            passed += 1
        else:
            failed += 1

    logger.info(f"\n📊 Resultados: {passed} passed, {failed} failed")
    return failed == 0


# ============================================================================
# TEST 4: Feature Flags
# ============================================================================

async def test_feature_flags():
    """Test 4: Verificar que los feature flags estén configurados."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Feature Flags")
    logger.info("="*70)

    from core.feature_flags import (
        USE_INTENT_CLASSIFICATION,
        USE_QUERY_EXPANSION,
        get_all_flags
    )

    all_flags = get_all_flags()

    logger.info("🚩 Estado de feature flags:")
    for flag_name, flag_value in all_flags.items():
        status = "✅" if flag_value else "⏸️ "
        logger.info(f"{status} {flag_name}: {flag_value}")

    # Verificar que los nuevos flags existan
    new_flags = [
        "USE_INTENT_CLASSIFICATION",
        "USE_QUERY_EXPANSION"
    ]

    all_present = all(flag in all_flags for flag in new_flags)

    if all_present:
        logger.info("\n✅ Todos los feature flags nuevos están configurados")
        return True
    else:
        logger.error("\n❌ Faltan algunos feature flags")
        return False


# ============================================================================
# TEST 5: Integración V2 Completa
# ============================================================================

async def test_v2_integration():
    """Test 5: Integración completa V2 (search + query_interpreter)."""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Integración V2 Completa")
    logger.info("="*70)

    try:
        from services.query_interpreter_service import query_interpreter
        from services.intent_classifier import get_intent_classifier

        if not query_interpreter:
            logger.warning("⚠️ QueryInterpreterService no está inicializado (saltando test)")
            return True

        classifier = get_intent_classifier()

        # Test queries críticos
        test_queries = [
            {
                "query": "tengo goteras en Quito",
                "expected_profession": "plomero",
                "expected_intent": "need_based"
            },
            {
                "query": "necesito un electricista",
                "expected_profession": "electricista",
                "expected_intent": "direct"
            }
        ]

        passed = 0
        failed = 0

        for test_case in test_queries:
            query = test_case["query"]
            expected_prof = test_case["expected_profession"]
            expected_intent = test_case["expected_intent"]

            logger.info(f"\n🔍 Test: '{query}'")

            # Clasificar intención
            intent = classifier.classify_intent(query)
            intent_value = intent.value if hasattr(intent, 'value') else intent

            # Interpretar query
            result = await query_interpreter.interpret_query_v2(
                user_message=query,
                city_context="Quito",
                expand_query=True
            )

            profession = result.get("profession")
            expansion_method = result.get("expansion_method")
            expanded_terms = result.get("expanded_terms")

            # Validar
            intent_ok = intent_value == expected_intent
            profession_ok = profession == expected_prof
            has_expansion = expanded_terms and len(expanded_terms) > 0

            intent_status = "✅" if intent_ok else "❌"
            profession_status = "✅" if profession_ok else "❌"
            expansion_status = "✅" if has_expansion else "❌"

            logger.info(f"   {intent_status} Intent: {intent_value} (expected: {expected_intent})")
            logger.info(f"   {profession_status} Profession: {profession} (expected: {expected_prof})")
            logger.info(f"   {expansion_status} Expanded: {len(expanded_terms) if expanded_terms else 0} terms ({expansion_method})")

            if intent_ok and profession_ok and has_expansion:
                passed += 1
            else:
                failed += 1

        logger.info(f"\n📊 Resultados: {passed} passed, {failed} failed")
        return failed == 0

    except Exception as e:
        logger.error(f"❌ Error en test de integración: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Función principal del script de testing."""
    logger.info("\n" + "="*70)
    logger.info("🧪 ENHANCED SEARCH V2 - TESTING SUITE")
    logger.info("Plan: Mejoras Inmediatas al Sistema de Búsqueda (Enero 2026)")
    logger.info("="*70)

    # Setup
    services = await setup_test_environment()
    if not services:
        logger.error("❌ No se pudo configurar el entorno de testing")
        return False

    # Ejecutar tests
    results = {}

    results["intent_classifier"] = await test_intent_classifier(services)
    results["query_expander"] = await test_query_expander(services)
    results["dynamic_catalog"] = await test_dynamic_catalog(services)
    results["feature_flags"] = await test_feature_flags()
    results["v2_integration"] = await test_v2_integration()

    # Resumen final
    logger.info("\n" + "="*70)
    logger.info("📊 RESUMEN FINAL DE TESTING")
    logger.info("="*70)

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\n🎯 Total: {passed_tests}/{total_tests} tests pasaron")

    if passed_tests == total_tests:
        logger.info("\n🎉 ¡TODOS LOS TESTS PASARON!")
        logger.info("\n✅ El sistema está listo para activar los feature flags:")
        logger.info("   export USE_INTENT_CLASSIFICATION=true")
        logger.info("   export USE_QUERY_EXPANSION=true")
        logger.info("   export USE_SYNONYM_LEARNING=true")
        logger.info("   docker compose restart ai-clientes")
        return True
    else:
        logger.warning("\n⚠️ Algunos tests fallaron - revisar los logs arriba")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
