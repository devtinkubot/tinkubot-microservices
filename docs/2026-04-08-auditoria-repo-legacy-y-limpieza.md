# Auditoría Profunda del Repo: Limpieza de Código Obsoleto, Muerto, Legacy y Archivos de Bajo Valor

Fecha: 2026-04-08

## Objetivo

Identificar, sin modificar runtime ni mover archivos, qué partes del repositorio parecen:

- legacy activo que todavía debe conservarse
- candidatas claras a limpieza futura
- artefactos locales o generados que ensucian el workspace
- documentación o archivos históricos que conviene reclasificar

El objetivo de este documento es servir como base para una futura limpieza controlada del repo.

## Alcance

Revisión realizada sobre:

- `python-services/`
- `nodejs-services/`
- `go-services/`
- `elixir-services/`
- `infrastructure-services/`
- `docs/`
- `thoughts/`

Método usado:

- inspección estructural del árbol del repo
- búsquedas repo-wide de señales `legacy`, `compat`, `bridge`, `wrapper`, `shim`, `fallback`
- revisión asistida por agentes para detectar legacy activo, candidatos de retiro y documentación histórica
- revisión de archivos trackeados por Git vs artefactos locales no trackeados

## Resumen Ejecutivo

Conclusiones principales:

1. El mayor foco de limpieza futura está en `python-services/ai-proveedores`, pero gran parte del código señalado como “legacy” sigue activo y no debe tratarse como basura.
2. La oportunidad más clara de limpieza estructural a nivel repo no está en Python sino en `elixir-services/provider-onboarding-worker/deps/`, que hoy contiene dependencias vendorizadas y trackeadas por Git.
3. El frontend mantiene un fallback legacy trackeado en `public/admin-dashboard.html`, mientras la aplicación actual vive en `apps/admin-dashboard/`.
4. El repo contiene muchos artefactos locales de caché y build en el workspace, pero en su mayoría no están versionados; deben separarse de la deuda real del repositorio.
5. La documentación de auditorías, planes y migraciones ya es suficientemente abundante como para requerir una política explícita de clasificación entre “vivo”, “transicional” e “histórico”.

## Hallazgos Prioritarios

### 1. Dependencias vendorizadas y trackeadas en `elixir-services/provider-onboarding-worker/deps/`

Hallazgo:

- El repo trackea contenido completo dentro de:
  - `/home/du/produccion/tinkubot-microservices/elixir-services/provider-onboarding-worker/deps/`

Evidencia:

- `git ls-files 'elixir-services/**'` muestra múltiples dependencias versionadas:
  - `deps/castore/*`
  - `deps/finch/*`
  - `deps/hpax/*`
  - `deps/jason/*`
  - `deps/mime/*`
  - `deps/mint/*`
  - `deps/nimble_options/*`
  - `deps/nimble_pool/*`
  - `deps/redix/*`
  - `deps/req/*`
  - `deps/telemetry/*`

Impacto:

- aumenta tamaño del repo
- mezcla código propio con código de terceros
- complica auditorías, búsquedas y mantenimiento
- eleva el costo de cambios y revisiones

Clasificación:

- `candidato fuerte de limpieza`

Recomendación:

- Validar si el vendoring fue intencional y todavía necesario.
- Si no lo es, planificar retiro de `deps/` trackeado y confiar en `mix.lock` + instalación reproducible.
- Si sí lo es, documentarlo explícitamente como decisión técnica para evitar que parezca basura accidental.

### 2. `ai-proveedores` concentra legacy activo, no necesariamente código muerto

Hallazgo:

- `ai-proveedores` tiene una superficie amplia de compatibilidad todavía viva, especialmente en maintenance.

Evidencia clara:

- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_menu.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_views.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_deletion.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_profile.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_services.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/wait_experience.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/wait_social.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/document_update.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/services_confirmation.py`

Además, el propio repo documenta que esto sigue vivo:

- `/home/du/produccion/tinkubot-microservices/docs/ai-proveedores-boundaries.md`
- `/home/du/produccion/tinkubot-microservices/docs/provider-contexts/audit.md`
- `/home/du/produccion/tinkubot-microservices/docs/provider-contexts/state-audit.md`
- `/home/du/produccion/tinkubot-microservices/docs/provider-contexts/decisions.md`

Impacto:

- estas piezas aumentan complejidad
- pero siguen siendo parte de rutas runtime, tests y compatibilidad de estados

Clasificación:

- `legacy activo, conservar por ahora`

Recomendación:

- No tratarlas como dead code.
- Mantener un inventario explícito de qué `compat_*`, `awaiting_*` y bridges siguen vivos.
- Retirar solo cuando una búsqueda repo-wide confirme ausencia de lectores, escritores y tests dependientes.

### 3. Hay candidatos claros a limpieza futura dentro de `ai-proveedores`, pero requieren verificación

Hallazgo:

- La propia documentación del proyecto ya marca piezas que deberían retirarse cuando cierre la ventana de compatibilidad.

Evidencia:

- `/home/du/produccion/tinkubot-microservices/docs/provider-contexts/audit.md`
- `/home/du/produccion/tinkubot-microservices/docs/provider-contexts/decisions.md`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/FRONTERAS_FLUJO.md`

Candidatos señalados o inferidos desde docs:

- aliases y wrappers de compatibilidad una vez migrados los consumidores
- puentes de maintenance que todavía sirven onboarding
- backfills e invariantes históricas ya absorbidas por el modelo vivo

Ejemplos concretos para seguimiento:

- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/services/sesion_proveedor.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/services/shared/orquestacion_whatsapp.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/services/shared/ingreso_whatsapp.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/tools/maintenance/migrar_servicios_genericos_legacy.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/tools/backfill/12_drop_provider_experience_years.sql`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/tools/backfill/19_normalizar_estados_proveedores.sql`

Clasificación:

- `candidatos a retiro con validación previa`

Recomendación:

- Verificar consumo real antes de tocar.
- Usar una matriz con:
  - archivo
  - motivo de legado
  - consumidor actual
  - condición de retiro

### 4. Frontend conserva un fallback legacy trackeado y separado del dashboard actual

Hallazgo:

- El dashboard actual vive en:
  - `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/apps/admin-dashboard/`

- Pero sigue existiendo un fallback trackeado en:
  - `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/public/admin-dashboard.html`

Evidencia adicional:

- `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/index.js`
  - si no existe build, sirve la versión legacy desde `/public`

Indicadores textuales:

- “sirviendo versión legacy desde /public”
- “Este fallback legacy ya no incluye controles operativos de WhatsApp Web”

Impacto:

- duplica la superficie del dashboard
- introduce una versión degradada pero persistente del panel
- puede enmascarar fallos de build o despliegue

Clasificación:

- `candidato a consolidación futura`

Recomendación:

- Mantenerlo mientras siga siendo fallback operativo.
- Documentar criterio de retiro:
  - cuándo el build del dashboard puede considerarse obligatorio
  - cuándo el fallback ya no debe existir

### 5. `go-services/wa-gateway` parece estable, pero arrastra documentación de migración como documentación cuasi-operativa

Hallazgo:

- El gateway tiene dos documentos muy cercanos en propósito:
  - `/home/du/produccion/tinkubot-microservices/go-services/wa-gateway/IMPLEMENTATION_SUMMARY.md`
  - `/home/du/produccion/tinkubot-microservices/go-services/wa-gateway/MIGRATION_SUMMARY.md`

Impacto:

- no es código muerto
- pero sí documentación transicional que puede quedar indefinidamente como si fuera parte del estado operativo

Clasificación:

- `histórico útil / revisar consolidación`

Recomendación:

- Evaluar si uno de los dos debe pasar a histórico explícito y el otro quedar como resumen operativo.

### 6. `ai-clientes` conserva compatibilidad legacy en modelos y persistencia, pero no aparece como deuda crítica

Hallazgo:

- Hay normalización de estados y estructuras legacy en:
  - `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/models/estados/flujo_conversacional.py`
  - `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/infrastructure/persistencia/repositorio_flujo.py`
  - `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/infrastructure/clientes/busqueda.py`

Impacto:

- parece compatibilidad funcional, no basura huérfana
- conviene revisarlo, pero no hay evidencia suficiente para proponer borrado

Clasificación:

- `legacy activo, conservar por ahora`

Recomendación:

- incluirlo en una segunda pasada de reducción de compatibilidad
- no mezclarlo con cleanup de alto riesgo en `ai-proveedores`

## Artefactos Locales y Generados Detectados

### 7. El workspace contiene muchos artefactos de caché y build

Se detectaron en el árbol:

- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `node_modules/`
- `dist/`
- `_build/`

Ejemplos:

- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/__pycache__/`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/.pytest_cache/`
- `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/node_modules/`
- `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/apps/admin-dashboard/dist/`
- `/home/du/produccion/tinkubot-microservices/elixir-services/provider-onboarding-worker/_build/`

Importante:

- La mayoría de estos artefactos no parecen estar trackeados por Git.
- No deben confundirse con deuda real del repositorio.

Clasificación:

- `ruido local de workspace`

Recomendación:

- Mantenerlos fuera del plan de limpieza del código fuente.
- Revisar solo si hay fallas de ignore o contaminación accidental de commits.

### 8. Hay backups de skills dentro de `.agents/skills`

Se encontraron:

- `/home/du/produccion/tinkubot-microservices/.agents/skills/braintrust-analyze/SKILL.md.bak`
- `/home/du/produccion/tinkubot-microservices/.agents/skills/research/SKILL.md.bak`

Impacto:

- no afectan runtime de negocio
- sí suman ruido y duplicación dentro del repo

Clasificación:

- `candidato menor de limpieza`

Recomendación:

- Confirmar si `.bak` debe vivir en el repo o pasar a working artifacts ignorados.

## Documentación y Archivos Históricos Relacionados con Limpieza

### 9. El repo ya acumula auditorías y planes de limpieza

Ejemplos:

- `/home/du/produccion/tinkubot-microservices/docs/2026-04-08-auditoria-repo-obsolescencia.md`
- `/home/du/produccion/tinkubot-microservices/docs/2026-04-08-auditoria-repo-limpieza-documentacion-y-legacy.md`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/AUDITORIA_CONTEXTOS_BACKEND.md`
- `/home/du/produccion/tinkubot-microservices/docs/plans/2026-04-02-component-based-bounded-contexts.md`

Impacto:

- útil para trazabilidad
- pero también puede fragmentar la fuente de verdad si no hay índice claro

Clasificación:

- `histórico útil / requiere curación`

Recomendación:

- mantener un índice de auditorías activas vs históricas
- evitar generar planes paralelos con el mismo propósito sin enlazarlos entre sí

## Clasificación Consolidada

### A. Conservar por ahora

- `python-services/ai-proveedores/routes/maintenance/compat_*`
- `python-services/ai-proveedores/flows/maintenance/wait_*`
- `python-services/ai-proveedores/services/sesion_proveedor.py`
- `python-services/ai-proveedores/services/shared/orquestacion_whatsapp.py`
- `python-services/ai-proveedores/services/shared/ingreso_whatsapp.py`
- compatibilidad legacy en `ai-clientes`
- fallback legacy del dashboard si sigue siendo requisito operativo real

### B. Candidatos fuertes de limpieza futura

- `elixir-services/provider-onboarding-worker/deps/` versionado
- backups `.bak` en `.agents/skills/`
- documentos de migración o resumen que ya no deban vivir al mismo nivel que la documentación operativa

### C. Candidatos a retiro con validación previa

- tools y backfills legacy en `ai-proveedores`
- aliases y bridges documentados como temporales
- fallback del dashboard en `public/admin-dashboard.html`
- resúmenes históricos del gateway una vez consolidada su documentación estable

### D. Ruido local, no deuda estructural

- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `node_modules/`
- `dist/`
- `_build/`

## Recomendaciones Priorizadas

### Prioridad Alta

1. Auditar formalmente si `elixir-services/provider-onboarding-worker/deps/` debe seguir trackeado.
2. Mantener una lista repo-wide de `legacy activo` vs `candidato de retiro`.
3. Tratar `ai-proveedores` como cleanup prioritario, pero sin borrar wrappers o bridges todavía vivos.
4. Definir criterio de retiro para el fallback `public/admin-dashboard.html`.

### Prioridad Media

1. Consolidar documentación histórica de migración y auditorías.
2. Revisar backups `.bak` en `.agents/skills/`.
3. Crear una matriz de herramientas/backfills legacy por servicio.

### Prioridad Baja

1. Hacer una pasada específica sobre `ai-clientes` para ver cuándo puede retirarse la compatibilidad de estados legacy.
2. Revisar si `go-services/wa-gateway/*SUMMARY.md` debe consolidarse en un solo documento estable.

## Plan de Limpieza Propuesto

### Fase 1. Inventario y clasificación

- catalogar por servicio:
  - legacy activo
  - herramientas históricas
  - artefactos generados
  - documentación transicional

### Fase 2. Quick wins sin tocar runtime

- retirar o ignorar backups `.bak`
- decidir política sobre docs históricos
- validar si el vendoring Elixir sigue siendo necesario

### Fase 3. Reducción de compatibilidad

- empezar por `ai-proveedores`, retirando bridges solo cuando se confirme que no tienen lectores vivos

### Fase 4. Consolidación documental

- mantener un índice único de auditorías y limpieza
- marcar explícitamente qué documentos son:
  - canónicos
  - transicionales
  - históricos

## Referencias Clave

- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_menu.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/routes/maintenance/compat_profile.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/services/shared/orquestacion_whatsapp.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/services/shared/ingreso_whatsapp.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/infrastructure/persistencia/repositorio_flujo.py`
- `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/index.js`
- `/home/du/produccion/tinkubot-microservices/nodejs-services/frontend/public/admin-dashboard.html`
- `/home/du/produccion/tinkubot-microservices/go-services/wa-gateway/MIGRATION_SUMMARY.md`
- `/home/du/produccion/tinkubot-microservices/go-services/wa-gateway/IMPLEMENTATION_SUMMARY.md`
- `/home/du/produccion/tinkubot-microservices/elixir-services/provider-onboarding-worker/deps/`

## Cierre

El repo no parece tener una cantidad masiva de código muerto evidente listo para borrado inmediato. Lo que sí tiene es:

- mucho `legacy activo`
- compatibilidad transicional concentrada en `ai-proveedores`
- algunos artefactos históricos y de build que deberían reclasificarse
- una oportunidad fuerte de limpieza estructural en dependencias Elixir vendorizadas

La limpieza correcta aquí no es “borrar lo que suena viejo”, sino distinguir con precisión:

- qué sigue vivo
- qué es histórico
- qué es local
- y qué ya merece plan concreto de retiro
