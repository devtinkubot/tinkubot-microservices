#!/usr/bin/env python3
"""Tests manuales para Sprint 1.16"""
import sys
import os

# Agregar shared-lib al path
shared_lib_path = os.path.join(os.path.dirname(__file__), '..', 'shared-lib')
sys.path.insert(0, shared_lib_path)

import asyncio
import inspect
from datetime import datetime

# Ahora importar después de configurar el path
from services.session_service import verificar_timeout_sesion, actualizar_timestamp_sesion


async def run_all_tests():
    print("=" * 60)
    print("SPRINT 1.16 - TESTS DE VALIDACIÓN")
    print("=" * 60)
    print()

    # Test 6: Backward compatibility
    print("=== Test 6: Backward Compatibility ===")
    sig_verificar = inspect.signature(verificar_timeout_sesion)
    sig_actualizar = inspect.signature(actualizar_timestamp_sesion)

    print(f'verificar_timeout_sesion parámetros: {list(sig_verificar.parameters.keys())}')
    assert len(sig_verificar.parameters) == 3, 'Debe tener 3 parámetros'
    assert list(sig_verificar.parameters.keys()) == ['phone', 'flow', 'timeout_seconds'], 'Parámetros incorrectos'
    print('✅ verificar_timeout_sesion: signature correcta')

    print(f'actualizar_timestamp_sesion parámetros: {list(sig_actualizar.parameters.keys())}')
    assert len(sig_actualizar.parameters) == 1, 'Debe tener 1 parámetro'
    print('✅ actualizar_timestamp_sesion: signature correcta')
    print('=== Test 6: PASADO ✅ ===')
    print()

    # Test 2: No timeout
    print("=== Test 2: Sin Timeout ===")
    flow = {"last_seen_at_prev": datetime.utcnow().isoformat()}
    should_reset, response = await verificar_timeout_sesion("test_phone", flow)
    assert should_reset == False, "NO debe detectar timeout"
    assert response is None, "No debe tener respuesta"
    print('✅ Test 2: No timeout detectado correctamente')
    print('=== Test 2: PASADO ✅ ===')
    print()

    # Test 4: actualizar_timestamp_sesion
    print("=== Test 4: Actualizar Timestamp ===")
    flow = {"last_seen_at": "2024-01-01T00:00:00"}
    updated_flow = await actualizar_timestamp_sesion(flow)
    assert "last_seen_at" in updated_flow, "Debe tener last_seen_at"
    assert "last_seen_at_prev" in updated_flow, "Debe tener last_seen_at_prev"
    assert updated_flow["last_seen_at_prev"] == "2024-01-01T00:00:00", "Debe mover timestamp anterior"
    print('✅ Test 4: Actualización de timestamp correcta')
    print('=== Test 4: PASADO ✅ ===')
    print()

    print("=" * 60)
    print("TODOS LOS TESTS PASARON ✅")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
