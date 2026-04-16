# AUDITORIA DE VERIFICACION POST-REFACTOR
**Fecha:** 2026-04-16
**Planes auditados:** PLAN_1 (Python) + PLAN_2 (Frontend)

---

## RESUMEN EJECUTIVO

| Area | Veredicto | Severidad |
|------|-----------|-----------|
| Frontend (PLAN 2) | **LIMPIO** - providersManager.ts de 2,785 a 21 lineas | -- |
| Python services.py | **CRITICO** - Codigo duplicado, archivo CRECIO de 898 a 1,505 lineas | CRITICAL |
| Python disponibilidad.py | **BUG DE RUNTIME** - ImportError en callers de servicio_disponibilidad | CRITICAL |
| Python orquestador | **PARCIAL** - Delegacion dinamica via `__getattr__` persiste | HIGH |
| Acoplamiento circular | **LIMPIO** - Sin imports circulares detectados | -- |
| Type Safety frontend | **LIMPIO** - Cero `as any` o `@ts-ignore` en providers/ | -- |

---

## HALLAZGOS CRITICOS

### H-1: services.py DUPLICO su tamano en vez de reducirse

**Esperado:** Bajar de 898 lineas (~700 tras extraer data access).
**Real:** 1,505 lineas (crecio un 67%).

La IA agrego la clase `ManejadorServicios` (lineas 79-683) pero **NO elimino** las funciones standalone originales (lineas 961-1505). Ahora existe codigo idéntico dos veces:

| Funcion (Metodo de clase) | Linea | Duplicado standalone | Linea |
|---|---|---|---|
| `ManejadorServicios.manejar_accion_servicios` | 144 | `manejar_accion_servicios` | 961 |
| `ManejadorServicios.manejar_accion_servicios_activos` | 213 | `manejar_accion_servicios_activos` | 1031 |
| `ManejadorServicios.manejar_agregar_servicios` | 229 | `manejar_agregar_servicios` | 1048 |
| `ManejadorServicios.manejar_confirmacion_agregar_servicios` | 382 | `manejar_confirmacion_agregar_servicios` | 1201 |
| `ManejadorServicios.manejar_eliminar_servicio` | 599 | `manejar_eliminar_servicio` | 1420 |
| `ManejadorServicios._persistir_servicios_agregados` | 83 | `_persistir_servicios_agregados` | 780 |

**Complicador:** Los tests (`test_normalizacion_servicios_ia.py`) importan las funciones standalone, NO la clase. El router (`routes/maintenance/handlers/services.py`) usa la clase. Ambos caminos estan activos.

**ACCION:**
- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEAS: 961-1505 | ACCION: "Eliminar las 5 funciones standalone duplicadas (manejar_accion_servicios, manejar_accion_servicios_activos, manejar_agregar_servicios, manejar_confirmacion_agregar_servicios, manejar_eliminar_servicio)"`
- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEAS: 780-840 | ACCION: "Eliminar funcion standalone _persistir_servicios_agregados() que duplica el metodo de ManejadorServicios"`
- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEA: 957 | ACCION: "Eliminar _obtener_manejador_servicios() - hack self = _obtener_manejador_servicios() ya no se necesita si las funciones standalone se eliminan"`
- `ARCHIVO: python-services/ai-proveedores/tests/unit/test_normalizacion_servicios_ia.py | LINEAS: 16-20 | ACCION: "Actualizar imports del test para usar ManejadorServicios en vez de las funciones standalone eliminadas"`

---

### H-2: ImportError runtime - servicio_disponibilidad no existe en su modulo

El singleton `servicio_disponibilidad` fue comentado en `disponibilidad.py:1186`:
```python
# servicio_disponibilidad = ServicioDisponibilidad()
```

Pero 2 archivos lo importan como lazy import:

- `ARCHIVO: python-services/ai-clientes/flows/enrutador.py | LINEA: 508 | ACCION: "CRITICAL BUG - ImportError: `from services.proveedores.disponibilidad import servicio_disponibilidad` falla porque el singleton fue comentado. Reemplazar por inyeccion de dependencia o importar desde principal"`
- `ARCHIVO: python-services/ai-clientes/flows/busqueda_proveedores/ejecutor_busqueda_en_segundo_plano.py | LINEA: 100 | ACCION: "CRITICAL BUG - Mismo ImportError. La variable servicio_disponibilidad ya no existe en el modulo disponibilidad"`

**Nota:** Al ser lazy imports (dentro de funciones), el error solo se manifiesta cuando esos code paths se ejecutan en runtime, no al arrancar el servicio.

**Como se creo en principal.py:** `principal.py:145` crea `servicio_disponibilidad = ServicioDisponibilidad(repositorio_metricas=repositorio_metricas)` pero en el modulo `principal`, NO en `services.proveedores.disponibilidad`.

---

## HALLAZGOS HIGH

### H-3: _resolver_supabase_runtime() - Acceso a BD que deberia pasar por repositorio

- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEAS: 686-688, 866 | ACCION: "La funcion standalone _normalizar_servicios_ingresados() usa supabase = _resolver_supabase_runtime() para acceder a BD directamente. Si se elimina la funcion standalone (H-1), esto desaparece. Si no, migrar a repositorio"`
- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/specialty.py | LINEAS: 68, 185, 191 | ACCION: "_resolver_supabase_runtime() accede a deps.supabase directamente. Migrar a inyeccion de repositorio"`
- `ARCHIVO: python-services/ai-proveedores/flows/onboarding/handlers/servicios.py | LINEAS: 44, 238 | ACCION: "Mismo patron _resolver_supabase_runtime() accediendo a deps.supabase directamente"`

---

### H-4: Delegacion dinamica `__getattr__` en OrquestadorConversacional

- `ARCHIVO: python-services/ai-clientes/services/orquestador_conversacion.py | LINEAS: 276, 322, 331-336 | ACCION: "callbacks_source: Any + __getattr__ delega metodos desconocidos a OrquestadorRetrollamadas. Esto perpetua el patron que el PLAN 1 (paso 1.2.4) debia eliminar. Tipo Any oculta la interfaz"`
- `ARCHIVO: python-services/ai-clientes/principal.py | LINEAS: 173-184, 197 | ACCION: "OrquestadorRetrollamadas sigue instanciandose y pasandose como callbacks_source. Verificar si los metodos delegados (verificar_si_bloqueado, enviar_texto_whatsapp, resetear_flujo, etc.) pueden inyectarse directamente"`

---

## HALLAZGOS MEDIUM

### H-5: Alias backward-compatible en principal.py con TODO pendiente

- `ARCHIVO: python-services/ai-proveedores/principal.py | LINEAS: 70-73 | ACCION: "Los aliases `supabase = deps.supabase` tienen un TODO: eliminar en siguiente iteracion. Verificar cuantos archivos en produccion siguen usando estos aliases (grep `from principal import supabase` ya retorna 0, asi que los aliases pueden eliminarse)"`

### H-6: Comentario de codigo muerto en disponibilidad.py

- `ARCHIVO: python-services/ai-clientes/services/proveedores/disponibilidad.py | LINEA: 1186 | ACCION: "Eliminar linea comentada `# servicio_disponibilidad = ServicioDisponibilidad()`. Si algo necesita referenciarse, que lo haga via DI, no como zombie comentado"`

### H-7: _obtener_manejador_servicios() - Anti-patron `self = ...`

Las funciones standalone en services.py usan:
```python
self = _obtener_manejador_servicios()  # Crea nueva instancia en cada llamada
```
Esto significa cada invocacion crea un `ManejadorServicios(RepositorioServiciosSupabase(deps.supabase))` nuevo. No es un singleton real sino una fabrica oculta.

- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEAS: 789, 957, 1211, 1428 | ACCION: "Si se eliminan las funciones standalone (H-1), este anti-patron desaparece automaticamente"`

---

## HALLAZGOS LOW

### H-8: Type hints con `Any` en orquestador

- `ARCHIVO: python-services/ai-clientes/services/orquestador_conversacion.py | LINEA: 276 | ACCION: "`callbacks_source: Any` deberia ser tipado con Protocol o clase base para eliminar el Any"`
- `ARCHIVO: python-services/ai-proveedores/flows/maintenance/services.py | LINEAS: 236, 390 | ACCION: "`cliente_openai: Optional[Any]` y `servicio_embeddings: Optional[Any]` deberian tiparse con AsyncOpenAI y ServicioEmbeddings respectivamente"`

---

## LO QUE ESTA LIMPIO

### Frontend (PLAN 2) - APROBADO

| Check | Resultado |
|-------|-----------|
| `providersManager.ts` lineas | 21 (target: <200) - **SUPERADO** |
| `as any` en providers/ | 0 ocurrencias |
| `@ts-ignore` en providers/ | 0 ocurrencias |
| Modulos creados | 7/7 (Types, State, Api, Formatters, Renderer, Modals, EventHandlers) |
| Imports circulares | 0 detectados |
| API publica (`ProvidersManager.iniciar/recargar`) | Idéntica, sin cambios en main.ts |

### PLAN 1 - Eliminacion de imports dinamicos

| Check | Resultado |
|-------|-----------|
| `from principal import` en produccion | **0 ocurrencias** - LIMPIO |
| `self.supabase` en orquestador | **0 ocurrencias** - LIMPIO |
| `run_supabase` en orquestador | **0 ocurrencias** - LIMPIO |
| Repositorio de lead events creado y conectado | SI |
| Repositorio de metricas rotacion creado y conectado | SI |
| `dependencies.py` con DI centralizada | SI |

---

## CONTEO DE LINEAS vs PLAN

| Archivo | Antes | Esperado | Real | Veredicto |
|---------|-------|----------|------|-----------|
| `providersManager.ts` | 2,785 | <200 | 21 | SUPERADO |
| `orquestador_conversacion.py` | 1,075 | <1,075 | 977 | OK (redujo 9%) |
| `disponibilidad.py` | 1,268 | <1,268 | 1,186 | OK (redujo 6%) |
| `services.py` (ai-proveedores) | 898 | ~700 | **1,505** | **FRACASO - crecio 67%** |

---

## ACCIONES PRIORITARIAS (en orden)

1. **CRITICO:** Arreglar ImportError de `servicio_disponibilidad` en `enrutador.py:508` y `ejecutor_busqueda_en_segundo_plano.py:100` - esto crashea en runtime
2. **CRITICO:** Eliminar las ~545 lineas de funciones standalone duplicadas en `services.py` y actualizar tests
3. **HIGH:** Eliminar `_resolver_supabase_runtime()` de specialty.py y onboarding handlers (services.py se resuelve con H-1)
4. **HIGH:** Tipar `callbacks_source` y eliminar `__getattr__` del orquestador o documentar explicitamente como deuda tecnica
5. **MEDIUM:** Eliminar aliases backward-compatible en `principal.py:70-73` de ai-proveedores
6. **LOW:** Eliminar `Any` types residuales en signatures
