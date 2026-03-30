# Provider Onboarding Async

Este documento resume la política canónica del flujo async de onboarding de proveedores, con foco en el paso de servicios y la persistencia final en Supabase.

## Objetivo

El alta debe responder rápido al proveedor y dejar el trabajo costoso fuera del path interactivo.

## Flujo canónico

1. `ai-proveedores` recibe el texto crudo del servicio.
2. El chat confirma el paso y avanza sin esperar IA.
3. `ai-proveedores` publica un evento crudo en `Redis Streams`.
4. `provider-onboarding-worker` consume el evento.
5. El worker llama al endpoint interno de `ai-proveedores` para normalizar el servicio.
6. El worker persiste el resultado en Supabase.
7. El worker confirma el evento con `ACK`.

No existe un segundo salto por Redis entre normalización y persistencia.

## Políticas operativas

- El proveedor nunca espera a la IA para continuar el onboarding.
- El flujo no vuelve a pedir aclaraciones después de capturar el servicio.
- La transformación de servicios vive en `ai-proveedores`, pero su ejecución ocurre fuera del request path.
- El worker es el dueño del side effect final en Supabase.
- La persistencia debe ser idempotente por evento.
- El fallback es `best effort`, no bloqueo del onboarding.

## Revisión de catálogo

Cuando la IA no resuelve con suficiente confianza `domain_code` y `category_name`, el sistema no bloquea el onboarding.

- `provider_services` sigue siendo la tabla canónica del servicio del proveedor.
- `provider_service_catalog_reviews` guarda la sugerencia de la IA para revisión humana:
  - `suggested_domain_code`
  - `proposed_category_name`
  - `proposed_service_summary`
  - `review_reason`
  - `review_status = pending`
- Cuando la clasificación no tiene una coincidencia clara, el sistema puede hacer
  un segundo pase de Structured Outputs con `json_schema` y `strict: true` para
  proponer una sugerencia best-effort útil para admin.
- Esa sugerencia vive solo en la review y nunca reemplaza el dato canónico del
  servicio hasta que un humano lo apruebe.
- El worker dispara esa persistencia al resolver el servicio.
- Si un `provider_service` se elimina, la review asociada también se limpia para no dejar referencias colgando.
- Si el proveedor completo se elimina, se limpian sus servicios y sus reviews ligadas.

## Contrato de servicios

El evento de servicios debe transportar el dato crudo y el contexto mínimo:

- `provider_id`
- `phone`
- `checkpoint`
- `raw_service_text`
- `service_position`
- `idempotency_key`

La resolución interna puede devolver:

- `service_name`
- `service_summary`
- `domain_code`
- `category_name`
- `classification_confidence`
- `requires_review`
- `review_reason`

## Política de experiencia

`experience_range` es la única señal canónica de experiencia del proveedor.

- `experience_years` ya no forma parte del contrato vivo del proveedor.
- El onboarding y los consumidores deben leer y persistir solo `experience_range`.
- Si un flujo necesita mostrar experiencia, debe mostrar el rango legible, no un entero.

## Política de completitud del perfil

Para considerar un perfil profesional como completo, el sistema requiere:

- `experience_range` informado
- al menos `1` servicio válido asociado al proveedor

## Redis y DLQ

- `Redis Streams` es la cola principal del onboarding async.
- El DLQ histórico `provider_onboarding_events_dlq` fue retirado y no forma parte del runtime canónico.
- Si se introduce un DLQ nuevo en el futuro, debe documentarse como un artefacto distinto, con nombre y propósito propios.

## Fuente de verdad

- Supabase sigue siendo la fuente de verdad para el estado del proveedor.
- Redis mantiene la capa operativa.
- `ai-proveedores` conserva la lógica de negocio y normalización.
- `provider-onboarding-worker` conserva la persistencia asíncrona.
