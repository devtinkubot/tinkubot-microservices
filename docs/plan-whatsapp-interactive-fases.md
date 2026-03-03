# Plan: WhatsApp Interactive por Fases (Clientes ↔ Proveedores)

## Resumen
Para el flujo de selección de proveedores por WhatsApp, la mejor opción es **Interactive Media Carousel** con **fallback** al listado actual.
Además, se define política de **sin contacto directo** (no exponer números), usando acciones controladas por bot.

## Decisión
1. Usar **Media Carousel** para presentar proveedores.
2. No usar **Product Carousel** para este caso.
3. Implementar en fases con fallback para compatibilidad.

## Por qué no Product Carousel
- Está orientado a catálogo e-commerce (`catalog_id`, `product_retailer_id`).
- El caso actual es marketplace de servicios/proveedores.
- Incrementa complejidad operativa sin beneficio directo en esta etapa.

## Opción recomendada
### Media Carousel + fallback
- Tarjetas con imagen + resumen del proveedor.
- Botones de acción por tarjeta (quick replies).
- Si no hay soporte/caso inválido, degradar a lista textual actual.

---

## Fase 1 — Soporte técnico de carrusel

### Objetivo
Habilitar `ui.type="carousel"` en el gateway y transporte hacia Meta Cloud API.

### Cambios
- `go-services/wa-gateway/internal/webhook/types.go`
  - Extender `UIConfig` para cards de carrusel.
- `go-services/wa-gateway/internal/metawebhook/service.go`
  - Agregar `case "carousel"` en dispatch.
- `go-services/wa-gateway/internal/metaoutbound/client.go`
  - Implementar `SendCarousel(...)`.
  - Validaciones y fallback.

### Criterio de aceptación
- Payload válido enviado a Meta para carrusel.
- Si el payload no cumple, se usa fallback sin romper flujo.

---

## Fase 2 — UX de proveedores en carrusel

### Objetivo
Reemplazar (o complementar) listado textual de resultados por carrusel.

### Diseño de tarjeta
- Header: imagen del proveedor (si existe).
- Body: nombre, ciudad, experiencia/rating (resumen corto).
- Botones quick reply:
  - `provider_card_detail::<provider_id>`
  - `provider_card_select::<provider_id>`

### Cambios
- `python-services/ai-clientes/templates/proveedores/` (nuevo builder de carrusel o adaptación de listado).
- Punto de salida de `enviar_prompt_proveedor` para emitir carrusel.
- Fallback automático a listado actual si faltan datos críticos.

### Criterio de aceptación
- Usuario ve proveedores en carrusel.
- Selección por tarjeta mapea proveedor correcto por `provider_id`.
- Flujo actual sigue funcionando si no hay carrusel.

---

## Fase 3 — Política sin contacto directo

### Objetivo
Evitar compartir números directos entre cliente y proveedor.

### Política
- No enviar `wa.me/<numero>` ni número plano al cliente.
- Exponer solo acciones controladas:
  - Solicitar llamada
  - Enviar mensaje por plataforma
  - Confirmar interés

### Cambios
- `python-services/ai-clientes/services/proveedores/conexion.py`
- `python-services/ai-clientes/templates/proveedores/conexion.py`
- Registro de eventos/lead para trazabilidad (`lead_events`).

### Criterio de aceptación
- No se expone contacto directo en mensajes.
- Se mantiene trazabilidad de intención y contacto en eventos.

---

## Fase 4 — Robustez y medición

### Objetivo
Asegurar estabilidad y medir impacto.

### Pruebas
- Unit Go: serialización carrusel + fallback.
- Unit Python: builder de cards + parseo de IDs.
- E2E: búsqueda → carrusel → detalle/selección → conexión sin contacto directo.
- Regressions: lista textual y flujo actual intactos.

### Métricas
- Tasa de selección de proveedor.
- Tiempo a selección.
- Errores de envío interactivo.
- Tasa de fallback activado.

---

## IDs/contratos recomendados

### Quick reply IDs
- `provider_card_detail::<provider_id>`
- `provider_card_select::<provider_id>`

### Regla de mapeo
- Resolver siempre por `provider_id`, no por texto visible ni índice.

---

## Riesgos y mitigaciones
1. Compatibilidad parcial de clientes/cuentas con carrusel
Mitigación: fallback automático a lista/texto.

2. Tarjetas con datos incompletos (sin imagen, etc.)
Mitigación: plantilla tolerante + degradación por tarjeta/lista.

3. Fricción al quitar contacto directo
Mitigación: acciones claras en UI + SLA de respuesta + feedback loop.

---

## Resultado esperado
- UX más moderna y legible para elegir proveedores.
- Menor fricción en selección inicial.
- Control de privacidad y trazabilidad comercial sin exponer números directos.
