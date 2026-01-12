# Diagrama de Integración del Repository Pattern

## 🔄 Flujo de Datos: Código Existente vs Repositorio

### Antes (Código Existente)
```
┌─────────────────┐
│  ProviderFlow   │
│  (handlers)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  business_logic.py              │
│  - normalizar_datos_proveedor() │
│  - registrar_proveedor()        │
│    - run_supabase()             │
│    - .upsert()                  │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   Supabase      │
│   (providers)   │
└─────────────────┘
```

### Después (Con Repository Pattern)
```
┌─────────────────┐
│  ProviderFlow   │
│  (handlers)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  SupabaseProviderRepository     │
│  - create()                     │
│    - normalizar_datos_proveedor() ◄── REUTILIZA
│    - run_supabase()             ◄── REUTILIZA
│    - .upsert()                  │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   Supabase      │
│   (providers)   │
└─────────────────┘
```

## 🎯 Puntos Clave de Reutilización

### 1. `normalizar_datos_proveedor()`
**Ubicación:** `services/business_logic.py`

**Reutilizado en:** `repositories/provider_repository.py::create()`

```python
# En el repositorio
from services.business_logic import normalizar_datos_proveedor

async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
    # REUTILIZAMOS lógica existente
    datos_normalizados = normalizar_datos_proveedor(data)
    
    # Luego ejecutamos upsert
    result = await run_supabase(...)
    ...
```

**Beneficios:**
- ✅ No duplicamos código de normalización
- ✅ Mantenemos consistencia
- ✅ `business_logic.py` sigue funcionando

### 2. `run_supabase()`
**Ubicación:** `utils/db_utils.py`

**Reutilizado en:** Todos los métodos del repositorio

```python
# En el repositorio
from utils.db_utils import run_supabase

async def find_by_phone(self, phone: str):
    result = await run_supabase(
        lambda: self._supabase.table("providers")
        .select("*")
        .eq("phone", phone)
        .execute(),
        timeout=5.0,
        label="providers.find_by_phone",
    )
    ...
```

**Beneficios:**
- ✅ Wrapper async consistente
- ✅ Logging de performance automático
- ✅ Manejo de timeouts

### 3. Helper functions de `services_utils.py`
**Ubicación:** `utils/services_utils.py`

**Usados indirectamente** vía `normalizar_datos_proveedor()`:

- `sanitizar_servicios()` - Limpia lista de servicios
- `formatear_servicios()` - Convierte a string persistible
- `normalizar_texto_para_busqueda()` - Para city y profession
- `normalizar_profesion_para_storage()` - Expande abreviaturas

## 🔄 Migración Gradual (Sin Romper Nada)

### Fase 1: Repositorio Creado (✅ COMPLETADO)
```python
# Código existente sigue funcionando
from services.business_logic import registrar_proveedor
proveedor = await registrar_proveedor(supabase, datos)

# NUEVO: También puedes usar el repositorio
from repositories import SupabaseProviderRepository
repo = SupabaseProviderRepository(supabase)
proveedor = await repo.create(datos)
```

### Fase 2: Integrar en Handlers (Próximo)
```python
# En handlers/nuevo_handler.py
from repositories import SupabaseProviderRepository

async def nuevo_handler(phone, message):
    repo = SupabaseProviderRepository(supabase)
    
    # Usar repositorio
    proveedor = await repo.find_by_phone(phone)
    
    if not proveedor:
        # Crear nuevo
        proveedor = await repo.create(datos)
    
    return proveedor
```

### Fase 3: Command + Saga Pattern
```python
# En core/saga.py
from repositories import SupabaseProviderRepository
from core.commands import RegisterProviderCommand

saga = ProviderRegistrationSaga()
saga.add_command(RegisterProviderCommand(repository, data))

try:
    result = await saga.execute()
except Exception as e:
    await saga.rollback()  # Compensating transaction
    raise
```

## 📊 Comparativa de Enfoques

### Enfoque Actual (business_logic.py)
```python
# Pros:
✅ Funciona y está probado
✅ Conocido por el equipo
✅ Simple y directo

# Contras:
❌ Difícil de testear (Supabase acoplado)
❌ Lógica mezclada con acceso a datos
❌ Sin rollback automático
❌ Difícil de mockear
```

### Enfoque Nuevo (Repository Pattern)
```python
# Pros:
✅ Fácil de testear (mockeable)
✅ Separación de responsabilidades
✅ Preparado para Command/Saga
✅ Reutiliza código existente
✅ Interfaz clara y documentada

# Contras:
❌ Curva de aprendizaje inicial
❌ Más archivos (pero mejor organizados)
```

## 🧪 Testing: Antes vs Después

### Antes (Difícil)
```python
# Tenías que mockear Supabase directamente
def test_registrar_proveedor():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.upsert...
    # Muchos detalles de implementación...
```

### Después (Fácil)
```python
# Solo mockeas el repositorio
async def test_mi_handler():
    mock_repo = AsyncMock()
    mock_repo.create.return_value = {"id": "123", ...}
    
    # Inyectar dependencia
    result = await my_handler(data, repository=mock_repo)
    
    # Verificar
    mock_repo.create.assert_called_once()
```

## 📈 Métricas de Éxito

### Código Creado
- **731 líneas** en repositorio (interfaces + implementación)
- **430 líneas** en tests
- **15+ tests** implementados

### Código Reutilizado
- ✅ `normalizar_datos_proveedor()` - ~70 líneas reutilizadas
- ✅ `sanitizar_servicios()` - ~15 líneas reutilizadas
- ✅ `run_supabase()` - ~50 líneas reutilizadas

### Código NO Modificado
- ✅ `services/business_logic.py` - 251 líneas intactas
- ✅ `utils/services_utils.py` - 246 líneas intactas
- ✅ `utils/db_utils.py` - 50 líneas intactas
- ✅ `flows/` - sin cambios
- ✅ `handlers/` - sin cambios

**Total: ~550 líneas de código existente PRESERVADAS**

## 🎯 Próximos Pasos

1. **Integración en un handler real**
   - Elegir un handler simple para migrar
   - Hacer A/B testing con código antiguo
   - Medir performance

2. **Implementar Command Pattern**
   - Crear `core/commands.py`
   - Implementar `RegisterProviderCommand`
   - Agregar métodos `execute()` y `undo()`

3. **Implementar Saga Pattern**
   - Crear `core/saga.py`
   - Orquestar registro + upload de imágenes
   - Implementar compensating transactions

4. **Refactorizar business_logic.py**
   - Mover lógica a servicios de dominio
   - Usar repositorio como única fuente de datos
   - Mantener compatibilidad durante transición

## 📚 Referencias

- [Repository Pattern Martin Fowler](https://martinfowler.com/eaaCatalog/repository.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Plan Arquitectónico Completo](../../../.claude/plans/refactored-toasting-valley.md)
