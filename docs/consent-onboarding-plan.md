# Plan: Consentimiento y Registro de Entregables

## Objetivo

Implementar un flujo inicial que capture el consentimiento explícito del cliente antes de continuar con la solicitud de servicios, registrar una métrica diaria con los criterios solicitados y el resultado entregado, y evitar repetición de consentimientos en futuras interacciones.

## Alcance

- Presentar y persistir la aceptación de términos (con enlace legal) la primera vez que un número interactúa con el bot.
- Saltar el prompt de consentimiento en sesiones posteriores cuando el usuario ya aceptó.
- Registrar, por cada solicitud completada, un resumen: `cliente`, `criterios_solicitados`, `respuesta_tinkubot`.
- Mantener trazabilidad mínima de conversaciones, sin almacenar la interacción completa.

## Dependencias Externas

### Equipo de Persistencia
- Definir/confirmar la estructura donde se guardará `usuario_acepta_terminos`.
- Validar tabla o vista para almacenar la métrica (`cliente`, `criterios`, `respuesta_tinkubot`, `fecha`).
- Exponer endpoints o funciones auxiliares (si se requieren) para lectura/consulta de aceptaciones y métricas.

### Equipo Legal
- Entregar el texto oficial del consentimiento y la URL a la política / acuerdos de uso.
- Definir requisitos de auditoría (ej. timestamp, versión del documento aceptado).
- Confirmar validez del consentimiento por número (¿caduca?, ¿se debe registrar versión?).

### Stakeholders / Producto (Tú)
- Priorizar el orden de implementación (consentimiento vs. métricas).
- Aprobar mensajes y tono comunicacional (copy de aceptación + enlaces).
- Validar el formato del resumen diario y su frecuencia de exportación.

## Trabajo del Equipo de Desarrollo (nosotros)

1. **Diseño técnico del flujo**
   - Añadir estado `awaiting_consent` y bandera `accepted_terms` en la sesión.
   - Definir fallback para usuarios que declinan (mensaje de despedida + reset).

2. **Persistencia de consentimientos/métricas**
   - Guardar el consentimiento con timestamp y versión.
   - Implementar la captura del resumen diario en la base definida por Persistencia.

3. **Integración y pruebas**
   - Ajustar pruebas en QA: casos aceptar/declinar, reingreso posterior, métricas.
   - Validar que los prompts posteriores usen la bandera `accepted_terms`.

4. **Entrega y documentación**
   - Actualizar `docs/OPERATIONS.md` con el nuevo flujo.
   - Documentar endpoints/tablas nuevas en caso de ser expuestas.
   - Coordinar con Legal la evidencia (logs, reportes) requerida para auditoría.

## Próximos pasos

1. Obtener copy final de consentimiento + enlace (Legal/Product).
2. Alinear con Persistencia la tabla/estructura para consentimientos y métricas.
3. Diseñar el flujo detallado (diagrama o pseudoestado) y validarlo contigo.
4. Implementar y probar en QA.
5. Habilitar reporte diario (automático o manual) para el resumen `cliente/criterios/respuesta`.

