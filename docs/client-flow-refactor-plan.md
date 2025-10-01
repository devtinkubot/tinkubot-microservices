# Plan de Migración de Flujos (Atención al Cliente)

## Objetivo

Completar la extracción de la lógica conversacional de `main.py` hacia `flows/client_flow.py`, modularizando cada estado y dejando a `main.py` como orquestador.

## Estados pendientes

1. `awaiting_location`
   - Validar coordenadas recibidas.
   - Enviar de nuevo el prompt de ubicación si faltan datos.
   - Pasar a `searching` cuando haya lat/lng válidos.

2. `searching`
   - Invocar `do_search()` centralizado en `ClientFlow` o mantener helper en `main.py` pero con llamada desde `ClientFlow`.
   - Manejar respuestas de búsqueda (sin proveedores / con proveedores).

3. `presenting_results`
   - Normalizar selecciones (número o texto “Conectar con…”).
   - Guardar el proveedor elegido y delegar la construcción del mensaje de conexión.

4. `confirm_new_search`
   - Interpretar respuestas “sí/no”, manejar intentos y despedida.
   - Resetear flujo y reenviar prompts cuando corresponda.

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

