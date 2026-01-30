# Diagrama de Arquitectura - Capa de Servicios

## Antes (main.py monolítico)

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py (1959 líneas)                    │
├─────────────────────────────────────────────────────────────────┤
│  🔀 Lógica de negocio mezclada con:                              │
│  - Búsqueda de proveedores                                       │
│  - Validación con IA                                             │
│  - Expansión de sinónimos                                        │
│  - Extracción de profesión/ubicación                            │
│  - Handlers HTTP                                                 │
│  - Configuración                                                 │
│  - Coordinación de disponibilidad                                │
│  - Scheduler                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Después (Clean Architecture con Service Layer)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     main.py (HTTP + Config)                      │   │
│  │  - FastAPI endpoints                                             │   │
│  │  - Configuración de servicios                                    │   │
│  │  - Inyección de dependencias                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SERVICE LAYER (DOMINIO)                         │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────┐ │
│  │  BuscadorProveedores │  │ ValidadorProveedoresIA│ │ ExpansorSinonimos│ │
│  │                      │  │                       │  │               │ │
│  │  + buscar()          │  │  + validar_proveedores│ │  + expandir()  │ │
│  │  127 líneas          │  │  209 líneas           │ │  430 líneas   │ │
│  └──────────────────────┘  └──────────────────────┘  └───────────────┘ │
│                                                                          │
│  Responsabilidades:                                                     │
│  - Buscador: Coordinar búsqueda + validación                            │
│  - Validador: Filtrar proveedores con IA                                │
│  - Expansor: Extraer y expandir términos                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ ClienteBusqueda  │  │   AsyncOpenAI    │  │ ClienteRedis         │  │
│  │ (HTTP Client)    │  │   (OpenAI API)   │  │ (Persistence)        │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│                                                                          │
│  - Integración con servicios externos                                   │
│  - Clientes HTTP                                                        │
│  - Persistencia                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Flujo de Datos

### Búsqueda de Proveedores

```
Usuario → main.py → OrquestadorConversacional
                    │
                    ▼
            ┌───────────────────────┐
            │ BuscadorProveedores   │
            │   .buscar()           │
            └───────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────┐      ┌──────────────────┐
│ ClienteBusqueda│     │ExpansorSinonimos │
│ (Search API)  │     │  (Términos IA)   │
└──────────────┘      └──────────────────┘
        │                       │
        └───────────┬───────────┘
                    ▼
            ┌───────────────────────┐
            │ ValidadorProveedoresIA│
            │   .validar_proveedores│
            └───────────────────────┘
                    │
                    ▼
            Proveedores Filtrados
```

## Separación de Responsabilidades

### BuscadorProveedores (127 líneas)
**Propósito:** Coordinar búsqueda de proveedores

```python
class BuscadorProveedores:
    """
    Coordina:
    1. Búsqueda en Search Service (token-based, rápido)
    2. Validación con IA (filtrado de resultados)
    3. Retorno de proveedores relevantes
    """

    def buscar(
        profesion: str,
        ciudad: str,
        radio_km: float,
        terminos_expandidos: List[str]
    ) -> Dict[str, Any]:
        # 1. Construir query con términos expandidos
        # 2. Llamar ClienteBusqueda.search_providers()
        # 3. Validar con ValidadorProveedoresIA
        # 4. Retornar proveedores filtrados
```

**Beneficios:**
- ✅ Búsqueda y validación separadas
- ✅ Fácil testing (mock search_client y ai_validator)
- ✅ Cambio de estrategia de búsqueda sin tocar validación

### ValidadorProveedoresIA (209 líneas)
**Propósito:** Validar relevancia de proveedores con IA

```python
class ValidadorProveedoresIA:
    """
    Valida:
    1. ¿El proveedor PUEDE ayudar con la necesidad?
    2. ¿Sus servicios son RELEVANTES?
    3. ¿Su experiencia es APLICABLE?

    Usa GPT-3.5 para analizar:
    - Profesión del proveedor
    - Servicios que ofrece
    - Experiencia
    """

    def validar_proveedores(
        user_need: str,
        providers: List[Dict]
    ) -> List[Dict]:
        # 1. Construir prompt con info de proveedores
        # 2. Llamar OpenAI API
        # 3. Parsear respuesta JSON
        # 4. Filtrar proveedores validados
```

**Beneficios:**
- ✅ Validación aislada y testeable
- ✅ Cambio de modelo de IA (GPT-4) sin afectar búsqueda
- ✅ Prompt engineering centralizado

### ExpansorSinonimos (430 líneas)
**Propósito:** Extraer y expandir términos de búsqueda

```python
class ExpansorSinonimos:
    """
    Extrae y expande:
    1. Extracción estática (rápida, sin IA)
    2. Extracción con IA (fallback)
    3. Expansión de sinónimos con IA

    Soporta:
    - Sinónimos de profesiones en español/inglés
    - Ciudades de Ecuador
    """

    def extraer_profesion_y_ubicacion_con_expansion(
        historial_texto: str,
        ultimo_mensaje: str
    ) -> Tuple[str, str, List[str]]:
        # 1. Intentar extracción estática
        # 2. Si falla, usar IA para extraer
        # 3. Expandir con IA para generar sinónimos
        # 4. Retornar (profesion, ubicacion, terminos_expandidos)
```

**Beneficios:**
- ✅ Extracción y expansión separadas
- ✅ Estrategia de fallback (estático → IA)
- ✅ Cacheable y optimizable

## Métricas de Mejora

### Código Organizado
| Antes | Después |
|-------|---------|
| 1959 líneas en main.py | ~1550 líneas en main.py (-21%) |
| 766 líneas de servicios | 766 líneas en servicios (+nuevo) |
| Lógica mezclada | 3 servicios especializados |

### Testabilidad
| Componente | Testable Antes | Testable Ahora |
|------------|----------------|----------------|
| Búsqueda | ❌ Difícil (mezclado) | ✅ Fácil (aislado) |
| Validación IA | ❌ Acoplado a main | ✅ Inyección de dependencias |
| Expansión | ❌ Funciones globales | ✅ Servicio con mock |

### Mantenibilidad
| Aspecto | Antes | Después |
|---------|-------|---------|
| Cambiar algoritmo de búsqueda | 🔴 Modificar main.py | 🟢 Modificar BuscadorProveedores |
| Cambiar modelo de IA | 🔴 Modificar main.py | 🟢 Modificar ValidadorProveedoresIA |
| Agregar nueva estrategia de expansión | 🔴 Modificar main.py | �que Extender ExpansorSinonimos |
| Testing unitario | 🔴 Difícil | 🟢 Fácil con mocks |

## Patrones Aplicados

### 1. Service Layer Pattern
```python
# Capa de servicios coordina lógica de negocio
class BuscadorProveedores:
    def __init__(self, search_client, ai_validator, logger):
        # Inyección de dependencias
```

### 2. Dependency Injection
```python
# main.py inyecta dependencias
buscador = BuscadorProveedores(
    search_client=search_client,
    ai_validator=validador,
    logger=logger
)
```

### 3. Single Responsibility
```python
# Cada servicio tiene UNA responsabilidad clara
BuscadorProveedores      → Coordinar búsqueda
ValidadorProveedoresIA   → Validar con IA
ExpansorSinonimos        → Expandir términos
```

### 4. Open/Closed Principle
```python
# Abiertos para extensión, cerrados para modificación
class ValidadorProveedoresIA:
    # Podemos cambiar el modelo de IA sin modificar la interfaz
```

## Próximos Pasos Recomendados

### Fase 1: Integración (Inmediata)
1. ✅ Crear servicios (COMPLETADO)
2. ⏭️ Actualizar main.py startup_event
3. ⏭️ Actualizar orquestador_conversacion.py
4. ⏭️ Verificar funcionalidad

### Fase 2: Limpieza (Después de verificar)
5. ⏭️ Eliminar funciones globales de main.py
6. ⏭️ Actualizar imports
7. ⏭️ Verificar que no hay regresiones

### Fase 3: Mejora (Opcional)
8. ⏭️ Agregar tests unitarios
9. ⏭️ Agregar métricas y tracing
10. ⏭️ Documentar arquitectura

## Conclusión

La nueva arquitectura sigue principios SOLID y Clean Architecture:

✅ **Separación de responsabilidades** - Cada servicio tiene una responsabilidad clara
✅ **Bajo acoplamiento** - Servicios se comunican vía interfaces
✅ **Alta cohesión** - Lógica relacionada está junta
✅ **Testabilidad** - Fácil testear con mocks
✅ **Mantenibilidad** - Cambios localizados
✅ **Escalabilidad** - Fácil agregar nuevos servicios
