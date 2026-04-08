# Auditoría de Contextos y Plan de Mejora de Fronteras en `ai-proveedores`

## Resumen Ejecutivo

Esta auditoría revisa la separación de contextos en `python-services/ai-proveedores`, con foco principal en `onboarding` y `maintenance`, e identifica si existen otros contextos de negocio y si el código actual comparte únicamente lo estrictamente necesario o genérico.

Conclusión general:

- La separación estructural existe y es visible.
- La implementación actual todavía presenta fugas entre contextos.
- El servicio está parcialmente separado, no completamente aislado.

## Objetivo del Documento

Entregar al equipo backend una base clara para revisar:

- qué contextos de negocio existen realmente
- qué fronteras están bien definidas
- dónde hay acoplamiento indebido
- qué mejoras conviene priorizar para endurecer límites

Este documento es solo de auditoría y plan de mejora. No propone cambios de código concretos ni incluye implementación.

## Contextos de Negocio Detectados

Los contextos de negocio reales identificados en el servicio son:

- `onboarding`
- `review`
- `maintenance`
- `availability`

Referencias:

- `python-services/ai-proveedores/FRONTERAS_FLUJO.md`
- `python-services/ai-proveedores/FLUJO_SISTEMA.md`
- `python-services/ai-proveedores/routes/onboarding/router.py`
- `python-services/ai-proveedores/routes/review/router.py`
- `python-services/ai-proveedores/routes/maintenance/router.py`
- `python-services/ai-proveedores/routes/availability/router.py`

## Capas Transversales Detectadas

Las siguientes piezas no deberían considerarse contextos de negocio independientes:

- `services/shared/`
- `services/sesion_proveedor.py`
- `flows/router.py`
- `principal.py`

Estas piezas cumplen funciones transversales, pero algunas hoy concentran más lógica de negocio de la deseable.

## Hallazgos

### 1. `onboarding` está bien delimitado a nivel estructural, pero no aislado

La estructura del contexto es consistente:

- `routes/onboarding/`
- `flows/onboarding/`
- `services/onboarding/`
- `templates/onboarding/`

Sin embargo, existe una fuga activa de dominio:

- `python-services/ai-proveedores/services/onboarding/registration/catalogo_servicios.py`

Ese módulo importa lógica desde:

- `services.maintenance.validacion_semantica`

Esto implica que `onboarding` depende de lógica operativa de `maintenance`, cuando debería apoyarse solo en contratos genéricos o lógica propia.

### 2. `maintenance` mantiene puentes legacy de `onboarding`

La estructura de `maintenance` también es explícita:

- `routes/maintenance/`
- `flows/maintenance/`
- `services/maintenance/`
- `templates/maintenance/`

Pero todavía arrastra compatibilidad que mezcla responsabilidades:

- `python-services/ai-proveedores/routes/maintenance/compat_profile.py`
- `python-services/ai-proveedores/services/maintenance/actualizar_servicios.py`

Se detectan handlers y compatibilidades que siguen ligados a pasos de onboarding, lo que muestra que la frontera funcional existe, pero no está completamente saneada.

### 3. `review` es un contexto propio

`review` no es una simple transición técnica; tiene identidad de negocio:

- controla `pending_verification`
- decide respuesta, silencio o reanudación
- tiene rutas y servicios propios

Referencias:

- `python-services/ai-proveedores/routes/review/router.py`
- `python-services/ai-proveedores/services/review/`

### 4. `availability` es un contexto propio

`availability` también opera como contexto diferenciado:

- administra la espera de respuesta del proveedor
- controla salida o retorno a menú
- tiene router y servicios separados

Referencias:

- `python-services/ai-proveedores/routes/availability/router.py`
- `python-services/ai-proveedores/services/availability/`

### 5. `shared` comparte más de lo estrictamente genérico

La carpeta `services/shared/` debería limitarse a:

- utilidades puras
- normalizaciones mecánicas
- contratos estables y neutros
- helpers técnicos de identidad, parsing o interacción

Sin embargo, hoy contiene piezas que conocen demasiado de varios contextos.

Caso principal:

- `python-services/ai-proveedores/services/shared/orquestacion_whatsapp.py`

Ese módulo integra dependencias y decisiones relacionadas con:

- `onboarding`
- `maintenance`
- `availability`

Esto lo acerca más a una capa de composición de negocio que a un módulo genérico compartido.

### 6. La capa de sesión no es completamente neutral

Se detecta acoplamiento entre sesión y policy de negocio en:

- `python-services/ai-proveedores/services/sesion_proveedor.py`

Ese archivo depende de piezas de `review` y participa en respuestas relacionadas con onboarding o menú, por lo que no se comporta como una simple capa técnica de sincronización de estado.

### 7. La deuda cross-context está reconocida, pero sigue viva

Existe una whitelist explícita de cruces legacy en:

- `python-services/ai-proveedores/tests/unit/test_context_boundaries.py`

Además, la documentación reconoce puentes históricos en:

- `python-services/ai-proveedores/FRONTERAS_FLUJO.md`

Esto es positivo como visibilidad arquitectónica, pero confirma que el objetivo de aislamiento todavía no está cumplido.

## Evidencia Objetiva

La prueba de fronteras actualmente falla:

- `python-services/ai-proveedores/tests/unit/test_context_boundaries.py`

Resultado observado durante la revisión:

- se detecta un cruce nuevo no aprobado entre `services/onboarding/registration/catalogo_servicios.py` y `services.maintenance.validacion_semantica`

Esto impide afirmar que la separación entre contextos ya esté correctamente cerrada.

## Diagnóstico Final

Estado de los contextos:

- `onboarding`: parcialmente separado
- `maintenance`: parcialmente separado
- `review`: razonablemente separado
- `availability`: razonablemente separado

Estado de capas transversales:

- `shared`: sobredimensionado
- `session`: mezcla responsabilidad técnica con policy de negocio

Veredicto general:

- La arquitectura va en la dirección correcta.
- La separación por carpetas, routers y documentación está bien encaminada.
- La implementación todavía no cumple el objetivo de compartir solo lo estrictamente necesario o genérico.

## Plan de Mejoras

### Fase 1. Cerrar fugas activas

Objetivo:

- eliminar dependencias directas de `onboarding` hacia `maintenance`

Acciones a revisar por backend:

- resolver el caso de `services/onboarding/registration/catalogo_servicios.py`
- mover la validación compartida a un contrato neutral o reubicar la lógica en el contexto dueño
- restaurar el cumplimiento del test de fronteras

### Fase 2. Reducir puentes legacy entre `onboarding` y `maintenance`

Objetivo:

- eliminar compatibilidades que mantienen semántica de onboarding dentro de maintenance

Acciones a revisar por backend:

- inventariar módulos `compat_*`
- revisar `flows/maintenance/*` que actúan como puente de onboarding
- definir criterio de retiro para cada adaptador legacy

### Fase 3. Reencuadrar `shared`

Objetivo:

- limitar `shared` a utilidades estrictamente genéricas

Acciones a revisar por backend:

- separar helpers puros de la orquestación transversal
- extraer decisiones de negocio de `shared`
- evitar que `shared` conozca reglas específicas de estados o flujos por contexto

### Fase 4. Limpiar ownership de sesión

Objetivo:

- dejar `session` como capa técnica y no como policy layer

Acciones a revisar por backend:

- reducir `services/sesion_proveedor.py` a sincronización, lectura y rehidratación
- mover lógica de `review`, `onboarding` o menú al contexto dueño

### Fase 5. Endurecer gobernanza arquitectónica

Objetivo:

- evitar reincidencia de cruces entre contextos

Acciones a revisar por backend:

- mantener el test de fronteras como contrato obligatorio
- reducir gradualmente la whitelist legacy
- exigir revisión arquitectónica para nuevos imports cross-context
- documentar con precisión qué puede y qué no puede vivir en `shared`

## Criterios de Aceptación de la Mejora

La separación podrá considerarse correctamente resuelta cuando se cumpla lo siguiente:

- `onboarding` no importe lógica de negocio desde `maintenance`
- `maintenance` no importe lógica de negocio desde `onboarding`
- `shared` solo contenga contratos y utilidades genéricas
- `session` no contenga policy de negocio de contextos concretos
- `review` y `availability` se mantengan como contextos explícitos e independientes
- `test_context_boundaries.py` pase sin nuevos cruces
- la whitelist legacy se reduzca progresivamente

## Referencias para el Equipo Backend

- `python-services/ai-proveedores/FRONTERAS_FLUJO.md`
- `python-services/ai-proveedores/FLUJO_SISTEMA.md`
- `python-services/ai-proveedores/tests/unit/test_context_boundaries.py`
- `python-services/ai-proveedores/services/shared/orquestacion_whatsapp.py`
- `python-services/ai-proveedores/services/sesion_proveedor.py`
- `python-services/ai-proveedores/services/onboarding/registration/catalogo_servicios.py`
- `python-services/ai-proveedores/routes/maintenance/compat_profile.py`
- `python-services/ai-proveedores/services/maintenance/actualizar_servicios.py`

## Nota Final

Este documento no propone una refactorización detallada ni un orden técnico de commits. Su función es servir como insumo de revisión para backend, alineando el diagnóstico arquitectónico actual con una ruta de mejora enfocada en ownership claro, reducción de acoplamiento y compartición mínima de lógica común.
