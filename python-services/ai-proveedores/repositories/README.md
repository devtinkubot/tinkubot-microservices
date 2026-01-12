# Repository Pattern para Proveedores

Este módulo implementa el **Repository Pattern** para el acceso a datos de proveedores, siguiendo los principios SOLID (especialmente DIP - Dependency Inversion).

## 📁 Estructura de Archivos

```
repositories/
├── __init__.py              # Exportaciones públicas
├── interfaces.py            # Interface IProviderRepository + ProviderFilter
├── provider_repository.py   # Implementación con Supabase
└── README.md               # Esta documentación

tests/
├── test_provider_repository.py  # Tests unitarios
└── __init__.py

scripts/
└── repository_demo.py      # Script de demostración
```

## 🎯 Objetivos

1. **Abstraer el acceso a datos**: Ocultar detalles de implementación de Supabase
2. **Facilitar testing**: Permitir mockear el repositorio en tests
3. **Reutilizar código existente**: Integrarse con `business_logic.py` sin duplicar
4. **Preparar para refactoring**: Base para futuros patrones (Command, Saga)

## 🚀 Uso Básico

### 1. Importar el repositorio

```python
from repositories import SupabaseProviderRepository, ProviderFilter
```

### 2. Inicializar con cliente de Supabase

```python
from supabase import Client

# supabase_client ya configurado
repository = SupabaseProviderRepository(supabase_client)
```

### 3. Operaciones CRUD

#### Crear proveedor

```python
proveedor_data = {
    "phone": "+593987654321",
    "full_name": "Juan Pérez",
    "city": "Quito",
    "profession": "ingeniero electricista",
    "services_list": ["Electricidad", "Fontanería"],
    "experience_years": 5,
    "has_consent": True,
}

resultado = await repository.create(proveedor_data)
# Returns: Dict con el proveedor creado (incluye ID)
```

#### Buscar por teléfono

```python
proveedor = await repository.find_by_phone("+593987654321")
# Returns: Dict o None si no existe
```

#### Buscar por ID

```python
proveedor = await repository.find_by_id("provider-id")
# Returns: Dict o None si no existe
```

#### Actualizar

```python
actualizado = await repository.update(
    provider_id="provider-id",
    data={"rating": 4.8, "available": False}
)
# Returns: Dict con el proveedor actualizado
```

#### Eliminar

```python
await repository.delete("provider-id")
# Útil para rollback en transacciones
```

### 4. Consultas Avanzadas

#### Buscar con filtros

```python
filtros = ProviderFilter(
    city="Quito",
    profession="ingeniero",
    verified=True,
    min_rating=4.0
)

resultados = await repository.find_many(
    filters=filtros,
    limit=10,
    offset=0
)
# Returns: List[Dict]
```

#### Contar proveedores

```python
total = await repository.count(filters=filtros)
# Returns: int
```

#### Verificar existencia

```python
existe = await repository.exists_by_phone("+593987654321")
# Returns: bool
```

#### Toggle disponibilidad

```python
actualizado = await repository.toggle_availability("provider-id")
# Alterna available: True ↔ False
```

## 🔌 Integración con Código Existente

El repositorio **reutiliza** funciones de `business_logic.py`:

```python
from services.business_logic import normalizar_datos_proveedor

async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
    # Reutilizamos función existente
    datos_normalizados = normalizar_datos_proveedor(data)
    
    # Ejecutamos upsert con Supabase
    result = await run_supabase(...)
    ...
```

**Ventajas:**
- ✅ No duplicamos lógica de normalización
- ✅ Mantenemos consistencia con el código existente
- ✅ `business_logic.py` sigue funcionando sin cambios

## 🧪 Testing

### Ejecutar tests

```bash
# Todos los tests
pytest tests/test_provider_repository.py -v

# Tests específicos
pytest tests/test_provider_repository.py -k "test_create" -v

# Con coverage
pytest tests/test_provider_repository.py --cov=repositories --cov-report=html
```

### Mockear el repositorio

```python
from unittest.mock import AsyncMock

async def test_mi_handler():
    # Crear mock del repositorio
    mock_repo = AsyncMock()
    mock_repo.find_by_phone.return_value = {"id": "123", "phone": "+593..."}
    
    # Inyectar en el handler
    result = await my_handler("+593...", repository=mock_repo)
    
    # Verificar
    mock_repo.find_by_phone.assert_called_once_with("+593...")
```

## 📊 Principios SOLID Aplicados

### SRP (Single Responsibility)
- El repositorio **solo** se encarga del acceso a datos
- No contiene lógica de negocio (eso está en `services/`)

### OCP (Open/Closed)
- Abierto para extensión: puedes crear `MockProviderRepository` para tests
- Cerrado para modificación: no necesitas cambiar la interfaz

### LSP (Liskov Substitution)
- Cualquier implementación de `IProviderRepository` es intercambiable
- Puedes cambiar de Supabase a MongoDB sin romper el código

### ISP (Interface Segregation)
- Interfaz enfocada y cohesiva
- Métodos específicos para cada operación

### DIP (Dependency Inversion)
- El código de negocio depende de `IProviderRepository` (abstracción)
- No depende directamente de Supabase (implementación concreta)

## 🔄 Roadmap de Integración

### ✅ Fase 1: Repositorio Creado
- [x] Interfaces definidas
- [x] Implementación con Supabase
- [x] Tests unitarios
- [x] Documentación

### 🔵 Fase 2: Integración Gradual
- [ ] Usar repositorio en nuevos handlers
- [ ] Mantener `business_logic.py` para compatibilidad
- [ ] Migrar funcionalidad gradualmente

### 🟡 Fase 3: Command + Saga Pattern
- [ ] Crear comandos reversibles (RegisterProviderCommand)
- [ ] Implementar saga de registro con compensating transactions
- [ ] Rollback automático en fallos

### 🟠 Fase 4: Refactorización Completa
- [ ] Mover lógica de dominio a servicios
- [ ] Usar repositorio como única fuente de datos
- [ ] Deprecar acceso directo a Supabase

## 📖 Referencias

- [Plan arquitectónico completo](../../../.claude/plans/refactored-toasting-valley.md)
- [Código existente](../services/business_logic.py)
- [Tests](../tests/test_provider_repository.py)
- [Demo](../scripts/repository_demo.py)

## 💡 Tips

1. **Siempre usar await**: Todos los métodos del repositorio son asíncronos
2. **Manejar RepositoryError**: Captura esta excepción para errores de BD
3. **Usar filtros**: `ProviderFilter` hace queries más eficientes
4. **Verificar exists**: `exists_by_phone` es más rápido que `find_by_phone` si solo necesitas saber si existe

## 🐛 Troubleshooting

### Error: "Provider not found"
```python
# Verificar que el ID o teléfono son correctos
proveedor = await repository.find_by_phone(phone)
if not proveedor:
    raise ValueError(f"Proveedor {phone} no encontrado")
```

### Error: "Failed to create provider"
```python
# Revisar los datos de entrada
try:
    resultado = await repository.create(data)
except RepositoryError as e:
    logger.error(f"Error creando proveedor: {e}")
```

### Queries lentas
```python
# Usar filtros específicos en lugar de traer todo
filtros = ProviderFilter(city="Quito", verified=True)
resultados = await repository.find_many(filters=filtros, limit=10)
```
