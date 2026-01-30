# Capa de Servicios de Dominio Creada

## Fecha de Creación
2026-01-26

## Objetivo
Mover la lógica de negocio desde `main.py` (1959 líneas) a servicios de dominio especializados siguiendo Clean Architecture con Service Layer.

## Servicios Creados

### 1. BuscadorProveedores
**Ubicación:** `/services/buscador/buscador_proveedores.py`

**Responsabilidad:**
- Coordinar la búsqueda de proveedores con el Search Service
- Validar resultados con IA antes de retornarlos
- Manejar términos de búsqueda expandidos

**Métodos públicos:**
- `buscar(profesion, ciudad, radio_km, terminos_expandidos)`: Ejecuta búsqueda completa

**Lógica movida desde main.py:**
- `search_providers()` (líneas 1039-1118)

**Dependencias:**
- `ClienteBusqueda` (infrastructure/clients/busqueda.py)
- `ValidadorProveedoresIA` (services/validacion/)

---

### 2. ValidadorProveedoresIA
**Ubicación:** `/services/validacion/validador_proveedores_ia.py`

**Responsabilidad:**
- Validar que los proveedores encontrados REALMENTE puedan ayudar con la necesidad del usuario
- Analizar profesión y servicios de cada proveedor
- Filtrar proveedores no relevantes usando IA

**Métodos públicos:**
- `validar_proveedores(user_need, providers)`: Filtra proveedores relevantes

**Lógica movida desde main.py:**
- `ai_validate_providers()` (líneas 1120-1283)

**Características:**
- Usa OpenAI GPT-3.5-turbo para validación
- Analiza términos en español e inglés (ej: "community manager" = "gestor de redes sociales")
- Retorna solo proveedores validados

**Dependencias:**
- `AsyncOpenAI` (openai)
- `asyncio.Semaphore` (control de concurrencia)

---

### 3. ExpansorSinonimos
**Ubicación:** `/services/expansion/expansor_sinonimos.py`

**Responsabilidad:**
- Extraer profesión y ubicación del texto del usuario
- Expandir términos de búsqueda usando IA para generar sinónimos
- Combinar extracción estática con extracción IA

**Métodos públicos:**
- `extraer_servicio_y_ubicacion(historial_texto, ultimo_mensaje)`: Extracción estática
- `expandir_necesidad_con_ia(user_need, max_sinonimos)`: Expande términos con IA
- `extraer_servicio_y_ubicacion_con_expansion(historial_texto, ultimo_mensaje)`: Wrapper completo

**Lógica movida desde main.py:**
- `extraer_servicio_y_ubicacion()` (líneas 493-534)
- `expand_need_with_ai()` (líneas 537-648)
- `extraer_servicio_y_ubicacion_con_expansion()` (líneas 650-697)
- `_extract_profession_with_ai()` (líneas 699-758)
- `_extract_location_with_ai()` (líneas 760-826)

**Características:**
- Búsqueda estática primero (rápida, sin IA)
- Fallback a IA si extracción estática falla
- Genera sinónimos en español e inglés
- Mantiene diccionario de ciudades de Ecuador

**Dependencias:**
- `AsyncOpenAI` (openai, opcional)
- `COMMON_SERVICE_SYNONYMS`, `COMMON_SERVICES` (models/catalogo_servicios)

---

## Estructura de Directorios

```
services/
├── buscador/
│   ├── __init__.py
│   └── buscador_proveedores.py     # Coordinador de búsqueda
├── validacion/
│   ├── __init__.py
│   └── validador_proveedores_ia.py # Validación con IA
├── expansion/
│   ├── __init__.py
│   └── expansor_sinonimos.py       # Expansión de términos
├── sesiones/                       # (ya existía)
├── clientes/                       # (ya existía)
└── orquestador_conversacion.py     # (ya existía)
```

## Patrones Arquitectónicos Aplicados

### 1. Service Layer Pattern
- Cada servicio encapsula lógica de negocio específica
- Servicios son orquestadores que coordinan dependencias
- Lógica de negocio separada de infraestructura

### 2. Dependency Injection
- Todos los servicios reciben dependencias por constructor
- Fácil testing con mocks
- Bajo acoplamiento entre componentes

### 3. Single Responsibility Principle
- `BuscadorProveedores`: Solo coordina búsqueda
- `ValidadorProveedoresIA`: Solo valida con IA
- `ExpansorSinonimos`: Solo expande términos

### 4. Open/Closed Principle
- Servicios abiertos para extensión
- Cerrados para modificación (via interfaces/inyección)

## Mantenimiento de Comportamiento

### Características Preservadas
✅ Todos los `logger.info()` originales mantenidos
✅ Misma lógica de negocio (copia línea por línea)
✅ Mismos timeouts y configuraciones
✅ Mismo manejo de errores
✅ Mismos valores de retorno

### Mejoras Implementadas
- Tipado más fuerte con `typing`
- Docstrings completos en Google Style
- Separación clara de responsabilidades
- Inyección de dependencias
- Mejor testabilidad

## Próximos Pasos

### Pendientes
1. **Actualizar `main.py`**: Reemplazar funciones con servicios
2. **Actualizar `orquestador_conversacion.py`**: Inyectar nuevos servicios
3. **Agregar tests unitarios**: Para cada servicio
4. **Eliminar funciones duplicadas**: De `main.py` después de migración

### Integración Ejemplo

```python
# En main.py (startup_event)
from services.buscador import BuscadorProveedores
from services.validacion import ValidadorProveedoresIA
from services.expansion import ExpansorSinonimos

# Crear servicios
expansor = ExpansorSinonimos(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger
)

validador = ValidadorProveedoresIA(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger
)

buscador = BuscadorProveedores(
    search_client=search_client,
    ai_validator=validador,
    logger=logger
)

# Usar en lugar de funciones originales
# Antes: result = await search_providers(...)
# Ahora: result = await buscador.buscar(...)
```

## Métricas

### Código Movido
- **Líneas movidas desde main.py**: ~400 líneas
- **Reducción potencial de main.py**: ~20% del tamaño actual
- **Nuevos servicios**: 3 clases principales
- **Métodos públicos**: 6 métodos principales

### Complejidad
- **Antes**: Todo mezclado en main.py (1959 líneas)
- **Ahora**: Separado en 3 servicios especializados
- **Cobertura de lógica**: Búsqueda, Validación, Expansión

## Archivos Creados

1. `/services/buscador/__init__.py` - Exportaciones
2. `/services/buscador/buscador_proveedores.py` - 140 líneas
3. `/services/validacion/__init__.py` - Exportaciones
4. `/services/validacion/validador_proveedores_ia.py` - 260 líneas
5. `/services/expansion/__init__.py` - Exportaciones
6. `/services/expansion/expansor_sinonimos.py` - 420 líneas

**Total**: ~820 líneas de código bien organizado y documentado

## Notas Importantes

⚠️ **NO ejecutar código aún**
- Los servicios están creados pero NO integrados en main.py
- main.py aún tiene las funciones originales
- Se requiere actualizar los callbacks del orquestador

✅ **Validaciones realizadas**
- Todos los imports son correctos
- Tipos de datos preservados
- Dependencias disponibles
- Logger mantenido en todas las operaciones

📋 **Tareas siguientes recomendadas**
1. Integrar servicios en main.py startup_event
2. Actualizar orquestador_conversacion.py
3. Verificar que no haya regresiones
4. Eliminar funciones duplicadas de main.py
5. Agregar tests unitarios
