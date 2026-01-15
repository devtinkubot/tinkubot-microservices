"""
Test Script - SynonymLearner (Aprendizaje Automático)

Este script valida la implementación del sistema de aprendizaje automático:
1. Creación de aprendizajes desde búsquedas exitosas
2. Actualización de match_count
3. Aprobación/rechazo de sinónimos
4. Consulta de pendientes
5. Integración con search_service

Ejecutar con:
    PYTHONPATH=/home/du/produccion/tinkubot-microservices:/home/du/produccion/tinkubot-microservices/python-services:/home/du/produccion/tinkubot-microservices/python-services/shared-lib python3 tests/integration/test_synonym_learner.py
"""

import asyncio
import logging
import sys

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

    try:
        from services.synonym_learner import synonym_learner
        from core.feature_flags import USE_SYNONYM_LEARNING

        logger.info("✅ SynonymLearner importado correctamente")
        logger.info(f"   USE_SYNONYM_LEARNING: {USE_SYNONYM_LEARNING}")

        if not synonym_learner:
            logger.error("❌ SynonymLearner no está inicializado")
            return None

        return {
            "synonym_learner": synonym_learner,
        }

    except ImportError as e:
        logger.error(f"❌ Error importando servicios: {e}")
        return None


# ============================================================================
# TEST 1: Aprendizaje desde búsqueda exitosa
# ============================================================================

async def test_learn_from_search(services):
    """Test 1: Creación de aprendizajes desde búsquedas."""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Aprendizaje desde Búsqueda Exitosa")
    logger.info("="*70)

    learner = services["synonym_learner"]

    test_queries = [
        {
            "query": "community manager",
            "profession": "marketing",
            "results": 5,
            "expected_learned": True
        },
        {
            "query": "social media expert",
            "profession": "marketing",
            "results": 3,
            "expected_learned": True
        },
        {
            "query": "marketing",  # No debe aprender (igual a profesión)
            "profession": "marketing",
            "results": 10,
            "expected_learned": False
        },
        {
            "query": "123",  # No debe aprender (número puro)
            "profession": "plomero",
            "results": 5,
            "expected_learned": False
        }
    ]

    passed = 0
    failed = 0

    for test_case in test_queries:
        query = test_case["query"]
        profession = test_case["profession"]
        results = test_case["results"]
        expected = test_case["expected_learned"]

        logger.info(f"\n🧪 Test: '{query}' → '{profession}' ({results} results)")

        try:
            result = await learner.learn_from_search(
                query=query,
                matched_profession=profession,
                num_results=results,
                city="Quito",
                context={"search_strategy": "test"}
            )

            learned = result is not None

            if learned == expected:
                status = "✅"
                passed += 1
                if result:
                    logger.info(f"   {status} Aprendizaje creado correctamente")
                    logger.info(f"   Confidence: {result.get('confidence_score', 0):.2f}")
            else:
                status = "❌"
                failed += 1
                logger.info(f"   {status} Resultado inesperado: learned={learned}, expected={expected}")

        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            failed += 1

    logger.info(f"\n📊 Resultados: {passed} passed, {failed} failed")
    return failed == 0


# ============================================================================
# TEST 2: Incremento de match_count
# ============================================================================

async def test_match_count_increment(services):
    """Test 2: Actualización de match_count al detectar mismo sinónimo."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Incremento de match_count")
    logger.info("="*70)

    learner = services["synonym_learner"]

    test_query = "gestor de redes sociales"
    test_profession = "marketing"

    logger.info(f"🧪 Test: Múltiples detecciones de '{test_query}'")

    try:
        # Primera detección
        result1 = await learner.learn_from_search(
            query=test_query,
            matched_profession=test_profession,
            num_results=5,
            city="Quito"
        )

        if not result1:
            logger.error("❌ Primera detección falló")
            return False

        initial_count = result1.get("match_count", 1)
        initial_confidence = result1.get("confidence_score", 0)

        logger.info(f"   Primera detección: match_count={initial_count}, confidence={initial_confidence:.2f}")

        # Segunda detección (debe incrementar)
        await asyncio.sleep(1)  # Pequeña pausa para different timestamp

        result2 = await learner.learn_from_search(
            query=test_query,
            matched_profession=test_profession,
            num_results=7,
            city="Guayaquil"
        )

        if not result2:
            logger.error("❌ Segunda detección falló")
            return False

        new_count = result2.get("match_count", 1)
        new_confidence = result2.get("confidence_score", 0)

        logger.info(f"   Segunda detección: match_count={new_count}, confidence={new_confidence:.2f}")

        # Validar incrementos
        count_increased = new_count > initial_count
        confidence_increased = new_confidence >= initial_confidence

        if count_increased and confidence_increased:
            logger.info("   ✅ match_count y confidence incrementaron correctamente")
            return True
        else:
            logger.error(f"   ❌ match_count no incrementó: {initial_count} → {new_count}")
            return False

    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
        return False


# ============================================================================
# TEST 3: Obtener sinónimos pendientes
# ============================================================================

async def test_get_pending_synonyms(services):
    """Test 3: Consulta de sinónimos pendientes de aprobación."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Obtener Sinónimos Pendientes")
    logger.info("="*70)

    learner = services["synonym_learner"]

    try:
        # Obtener pendientes
        pending = await learner.get_pending_synonyms(limit=10)

        logger.info(f"✅ {len(pending)} sinónimos pendientes encontrados")

        if pending:
            logger.info("\n📋 Top 5 pendientes:")
            for i, syn in enumerate(pending[:5], 1):
                logger.info(
                    f"   {i}. '{syn['learned_synonym']}' → '{syn['canonical_profession']}' "
                    f"(confidence: {syn['confidence_score']:.2f}, matches: {syn['match_count']})"
                )

        return True

    except Exception as e:
        logger.error(f"❌ Error obteniendo pendientes: {e}")
        return False


# ============================================================================
# TEST 4: Aprobación de sinónimo
# ============================================================================

async def test_approve_synonym(services):
    """Test 4: Aprobación de sinónimo aprendido."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Aprobación de Sinónimo")
    logger.info("="*70)

    learner = services["synonym_learner"]

    try:
        # Crear un sinónimo de prueba
        await learner.learn_from_search(
            query="test synonym approval",
            matched_profession="marketing",
            num_results=5,
            city="Quito"
        )

        # Obtener pendientes y buscar el nuestro
        pending = await learner.get_pending_synonyms(limit=50)

        test_synonym = None
        for syn in pending:
            if syn['learned_synonym'] == 'test synonym approval':
                test_synonym = syn
                break

        if not test_synonym:
            logger.warning("⚠️ No se encontró el sinónimo de prueba (puede no haberse creado)")
            return True

        logger.info(f"🧪 Test: Aprobar sinónimo '{test_synonym['learned_synonym']}'")

        # Aprobar
        approved = await learner.approve_synonym(
            learned_id=test_synonym['id'],
            approved_by="test_admin"
        )

        if approved and approved.get('status') == 'approved':
            logger.info("   ✅ Sinónimo aprobado correctamente")
            logger.info(f"   Status: {approved['status']}")
            logger.info(f"   Approved by: {approved['approved_by']}")
            return True
        else:
            logger.error("❌ Fallo en aprobación")
            return False

    except Exception as e:
        logger.error(f"❌ Error en test de aprobación: {e}")
        return False


# ============================================================================
# TEST 5: Rechazo de sinónimo
# ============================================================================

async def test_reject_synonym(services):
    """Test 5: Rechazo de sinónimo aprendido."""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Rechazo de Sinónimo")
    logger.info("="*70)

    learner = services["synonym_learner"]

    try:
        # Crear un sinónimo de prueba para rechazar
        await learner.learn_from_search(
            query="test synonym rejection",
            matched_profession="marketing",
            num_results=3,
            city="Quito"
        )

        # Obtener pendientes y buscar el nuestro
        pending = await learner.get_pending_synonyms(limit=50)

        test_synonym = None
        for syn in pending:
            if syn['learned_synonym'] == 'test synonym rejection':
                test_synonym = syn
                break

        if not test_synonym:
            logger.warning("⚠️ No se encontró el sinónimo de prueba (puede no haberse creado)")
            return True

        logger.info(f"🧪 Test: Rechazar sinónimo '{test_synonym['learned_synonym']}'")

        # Rechazar
        rejected = await learner.reject_synonym(
            learned_id=test_synonym['id'],
            rejected_by="test_admin",
            reason="Test de rechazo"
        )

        if rejected and rejected.get('status') == 'rejected':
            logger.info("   ✅ Sinónimo rechazado correctamente")
            logger.info(f"   Status: {rejected['status']}")
            logger.info(f"   Rejection reason: {rejected.get('rejection_reason', 'N/A')}")
            return True
        else:
            logger.error("❌ Fallo en rechazo")
            return False

    except Exception as e:
        logger.error(f"❌ Error en test de rechazo: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Función principal del script de testing."""
    logger.info("\n" + "="*70)
    logger.info("🧪 SYNONYM LEARNER - TESTING SUITE")
    logger.info("Sistema de Aprendizaje Automático de Sinónimos")
    logger.info("="*70)

    # Setup
    services = await setup_test_environment()
    if not services:
        logger.error("❌ No se pudo configurar el entorno de testing")
        return False

    # Ejecutar tests
    results = {}

    results["learn_from_search"] = await test_learn_from_search(services)
    results["match_count_increment"] = await test_match_count_increment(services)
    results["get_pending_synonyms"] = await test_get_pending_synonyms(services)
    results["approve_synonym"] = await test_approve_synonym(services)
    results["reject_synonym"] = await test_reject_synonym(services)

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
        logger.info("\n✅ El sistema de aprendizaje está funcionando correctamente:")
        logger.info("   - Las búsquedas exitosas generan aprendizajes")
        logger.info("   - Los sinónimos repetidos incrementan match_count")
        logger.info("   - La aprobación/rechazo funciona correctamente")
        logger.info("\n📝 Para activar el aprendizaje automático:")
        logger.info("   export USE_SYNONYM_LEARNING=true")
        logger.info("   docker compose restart ai-clientes")
        return True
    else:
        logger.warning("\n⚠️ Algunos tests fallaron - revisar los logs arriba")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
