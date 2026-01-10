# Tests para ai-proveedores

Este directorio contiene los tests de contrato (endpoint tests) para el servicio ai-proveedores, creados como parte de la **Sprint-1.12 de refactorización**.

## Propósito

Estos tests aseguran que no haya **breaking changes** durante la refactorización del servicio. Verifican que todos los endpoints públicos mantengan su contrato actual:

- Status codes correctos
- Estructura de respuestas JSON
- Manejo apropiado de errores
- Compatibilidad con dependencias externas

## Estructura

```
tests/
├── __init__.py
├── conftest.py                 # Fixtures y configuración global
├── requirements-test.txt        # Dependencias de testing
├── api/
│   ├── __init__.py
│   └── test_endpoints.py        # Tests de todos los endpoints
└── README.md                    # Este archivo
```

## Endpoints Probados

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check del servicio |
| `/intelligent-search` | POST | Búsqueda inteligente de proveedores |
| `/send-whatsapp` | POST | Envío de mensajes WhatsApp |
| `/handle-whatsapp-message` | POST | Webhook principal de WhatsApp |
| `/api/v1/providers/{id}/notify-approval` | POST | Notificación de aprobación |
| `/providers` | GET | Obtener lista de proveedores |

## Instalación

### 1. Instalar dependencias de testing

```bash
cd /home/du/produccion/tinkubot-microservices/python-services/ai-proveedores
pip install -r tests/requirements-test.txt
```

### 2. Opcional: Instalar dependencias principales

```bash
pip install -r requirements.txt
```

## Ejecución

### Ejecutar todos los tests

```bash
pytest tests/ -v
```

### Ejecutar solo tests de endpoints

```bash
pytest tests/api/test_endpoints.py -v
```

### Ejecutar tests específicos

```bash
# Solo tests de health check
pytest tests/api/test_endpoints.py::TestHealthEndpoint -v

# Solo un test específico
pytest tests/api/test_endpoints.py::TestHealthEndpoint::test_health_check_returns_200 -v
```

### Ejecutar con coverage

```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term
```

### Ejecutar tests en paralelo (más rápido)

```bash
pip install pytest-xdist
pytest tests/ -n auto
```

### Ver output detallado

```bash
pytest tests/ -vv -s
```

## Convenciones de Tests

### Estructura de un Test

```python
def test_nombre_descriptivo(
    self,
    fixture1: Type1,
    fixture2: Type2,
    client: TestClient,
) -> None:
    """
    Docstring explicativo del test.

    Debe describir:
    - Qué se está probando
    - Qué se espera que suceda
    - Por qué es importante este test
    """
    # Arrange (preparar)
    # Act (actuar)
    # Assert (verificar)
```

### Categorías de Tests

1. **Tests de éxito**: Verifican comportamiento esperado (200, 201)
2. **Tests de error**: Verifican manejo de errores (400, 404, 500)
3. **Tests de estructura**: Validan schema de respuestas JSON
4. **Tests de edge cases**: Situaciones inusuales o extremas
5. **Tests de integración**: Flujos completos multi-endpoint

### Convenciones de Nombres

- Clases: `Test<NombreEndpoint>`
- Tests: `test_<acción>_<condición>_<resultado_esperado>`
- Ejemplo: `test_intelligent_search_success_returns_200`

## Mocking

Los tests usan mocks extensivamente para:

- **Supabase**: Evitar llamadas a base de datos real
- **OpenAI**: Evitar llamadas a la API (costo)
- **httpx**: Evitar llamadas HTTP externas
- **Redis**: Evitar dependencia de Redis real

### Ejemplo de Mock

```python
@patch("main.buscar_proveedores")
def test_intelligent_search_success(
    self, mock_buscar: AsyncMock, client: TestClient
) -> None:
    mock_buscar.return_value = [{"id": "123", "name": "Test"}]

    response = client.post("/intelligent-search", json={...})

    assert response.status_code == 200
    mock_buscar.assert_called_once()
```

## Fixtures Disponibles

En `conftest.py`:

- `client`: TestClient de FastAPI
- `mock_supabase`: Cliente Supabase mockeado
- `mock_openai`: Cliente OpenAI mockeado
- `mock_httpx_client`: Cliente httpx mockeado
- `sample_provider_data`: Datos de ejemplo de proveedor
- `sample_search_request`: Datos de ejemplo de búsqueda
- `sample_whatsapp_message`: Datos de ejemplo de mensaje WhatsApp

## Estrategia de Sprint-1.12

### Fase 1: Crear Tests (Actual) ✅

- [x] Crear estructura de tests
- [x] Crear tests para todos los endpoints
- [x] Verificar que todos los tests pasan

### Fase 2: Ejecutar Tests Baseline

```bash
# Ejecutar y guardar resultados baseline
pytest tests/api/test_endpoints.py -v > test-results-baseline.txt
```

### Fase 3: Refactorizar

- Refactorizar código con tests de seguridad
- Ejecutar tests después de cada cambio

### Fase 4: Verificar No Breaking Changes

```bash
# Comparar resultados con baseline
pytest tests/api/test_endpoints.py -v > test-results-after.txt
diff test-results-baseline.txt test-results-after.txt
```

## Troubleshooting

### Error: ModuleNotFoundError

```bash
# Asegurarse de estar en el directorio correcto
cd /home/du/produccion/tinkubot-microservices/python-services/ai-proveedores

# O agregar al PYTHONPATH
export PYTHONPATH="/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores:$PYTHONPATH"
```

### Error: ImportError en tests

Verificar que las dependencias estén instaladas:

```bash
pip install -r requirements.txt
pip install -r tests/requirements-test.txt
```

### Tests fallan con errores de conexión

Los tests NO deben hacer llamadas reales a APIs externas. Si un test intenta conectar:

1. Verificar que el mock esté configurado correctamente
2. Verificar que el path del mock sea correcto (ej: `"main.buscar_proveedores"`)
3. Revisar el traceback para ver qué llamada no está mockeada

### Tests pasan localmente pero fallan en CI

1. Verificar que todas las dependencias estén en `requirements.txt`
2. Verificar que no haya dependencias del sistema operativo
3. Revisar que los mocks no dependan del entorno local

## Mejoras Futuras

- [ ] Tests de carga (performance)
- [ ] Tests de integración con Supabase real (test database)
- [ ] Tests de contratos con otros servicios (wa-proveedores, etc.)
- [ ] Setup de CI/CD para ejecutar tests automáticamente
- [ ] Reporting de coverage con badge en README

## Contacto

Para preguntas o sugerencias sobre los tests, contactar al equipo de desarrollo.
