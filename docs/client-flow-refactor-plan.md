# Plan de Migración de Flujos (Atención al Cliente)

## Objetivo

Completar la extracción de la lógica conversacional de `main.py` hacia `flows/client_flow.py`, modularizando cada estado y dejando a `main.py` como orquestador.

## Estado actual

- [x] `awaiting_location` extraído a `ClientFlow` con validación de coordenadas y reintentos.
- [x] `searching` encapsulado en `ClientFlow.handle_searching`, incluida la transición a confirmaciones y persistencia en Supabase.
- [x] `presenting_results` migrado con normalización de selección y agenda de feedback.
- [x] `confirm_new_search` centralizado con manejo de intents, reset y despedida.

## TODO inmediato

1. Realizar pruebas manuales end-to-end en QA para validar el flujo completo tras la extracción.
2. Ajustar documentación operativa (`docs/OPERATIONS.md`) si la orquestación cambió para el equipo de soporte.
3. Evaluar si vale la pena introducir un `FlowContext` o helper similar para reducir la cantidad de callbacks que recibe `ClientFlow`.

## Pasos sugeridos

1. Extraer `awaiting_location` a `ClientFlow` (método que verifique lat/lng y devuelva `searching` o prompt de ubicación).
2. Crear método `handle_searching` que encapsule `do_search()` y devuelva la estructura esperada (mensajes, estado siguiente).
3. Mover `presenting_results` con métodos auxiliares para elegir proveedor y construir respuesta.
4. Migrar `confirm_new_search`, incorporando la lógica de intentos, despedida (`FAREWELL_MESSAGE`) y reset.
5. Una vez migrados todos, evaluar si `do_search()` debe vivir en `ClientFlow` o seguir como helper en `main.py`.

## Notas

- Mantener pruebas manuales en QA tras cada migración parcial.
- Actualizar documentación (`docs/OPERATIONS.md`) cuando cambie la estructura del flujo.
- Revisar si al final conviene clases auxiliares (ej. `FlowContext`) para reducir parámetros.
