# Auditoría: Dependencias Transversales en ai-proveedores

**Fecha:** 2026-04-17
**Ámbito:** `python-services/ai-proveedores/`
**Tipo:** Solo análisis (sin cambios de código)

## Contexto

Durante el refactor para separar contextos de negocio (onboarding, maintenance, etc.) surge el riesgo de duplicar código cuando varios contextos necesitan la misma lógica subyacente. Este documento mapea qué módulos de `services/` son consumidos por más de un contexto de `flows/` para decidir qué extraer a `shared/`.

## Estructura observada

**`/services/`:** `onboarding/`, `maintenance/`, `shared/`, `review/`, `availability/`, `metrics/`

**`/flows/` (contextos):** `onboarding/`, `maintenance/`, `validators/`, `session/`, `constructors/`

## Tabla de dependencias transversales

| Servicio/Función en `/services/` | Onboarding | Maintenance | Session | Validators | Constructors | Estado Sugerido |
|---|---|---|---|---|---|---|
| `redes_sociales_slots.py` | Sí | Sí | No | Sí | No | **EXTRAER a Shared** |
| `ubicacion_ecuador.py` | Sí | Sí | No | No | No | **EXTRAER a Shared** |
| `validacion_semantica.py` | Sí | Sí | No | No | No | **EXTRAER a Shared** |
| `shared/__init__.py::es_skip_value` | Sí | Sí | No | No | No | Confirmar uso (ya en shared) |
| `onboarding/whatsapp_identity.py` | Sí | No | Sí | No | No | EVALUAR (2 contextos) |
| `maintenance/identidad_proveedor.py` | No | Sí | No | No | Sí | EVALUAR (2 contextos) |
| `onboarding/estado_operativo.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `maintenance/estado_operativo.py` | No | Sí | No | No | No | MANTENER en maintenance |
| `shared/estados_proveedor.py` | No | No | Sí | No | No | MANTENER en shared |
| `shared/whatsapp_identity.py` | Sí | No | No | No | No | MANTENER en shared |
| `onboarding/event_payloads.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `onboarding/event_publisher.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `onboarding/consentimiento.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `onboarding/servicios.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `maintenance/asistente_clarificacion.py` | No | Sí | No | No | No | MANTENER en maintenance |
| `maintenance/constantes.py` | No | Sí | No | No | No | MANTENER en maintenance |
| `onboarding/registration/constantes.py` | Sí | No | No | No | No | MANTENER en onboarding |
| `review/messages.py` | No | No | No | No | Sí | MANTENER en review |

## Resumen ejecutivo

- **Acoplamiento:** ALTO con patrones mixtos. La estructura general onboarding/maintenance está bien segregada, pero hay duplicación en utilidades de validación y normalización.
- **Candidatos fuertes para `shared/`:** `redes_sociales_slots` (3 contextos), `ubicacion_ecuador` (2), `validacion_semantica` (2).
- **Señales de divergencia a revisar:** dos `estado_operativo.py` (onboarding vs maintenance) y dos `whatsapp_identity.py` (onboarding vs shared) — probablemente divergieron y deberían consolidarse.

## Hallazgos a atender (orden sugerido)

1. **Extraer `redes_sociales_slots.py` a `services/shared/`** (mayor impacto: 3 contextos).
2. **Extraer `ubicacion_ecuador.py` a `services/shared/`**.
3. **Extraer `validacion_semantica.py` a `services/shared/`** (nota: aparece como `D` en git status, verificar si ya fue movido/eliminado).
4. **Consolidar `estado_operativo.py`** — comparar ambas versiones, decidir si unificar o mantener separadas con nombre distinto.
5. **Consolidar `whatsapp_identity.py`** — decidir canónico entre `onboarding/` y `shared/`.
6. **Evaluar `identidad_proveedor.py`** — usado por maintenance + constructors.

## Metodología

Reconocimiento automático vía grep sobre imports (`from .*services`, `import .*services`) dentro de cada subdirectorio de `flows/`, cruzando con listado de módulos en `services/`. No se ejecutó ni modificó código.
