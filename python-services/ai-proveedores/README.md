# AI Proveedores

Servicio FastAPI encargado del alta, revisión y mantenimiento de proveedores.

## Mapa de arquitectura

La estructura física del servicio está organizada por responsabilidad:

- `config/`: parámetros de entorno y configuración operativa.
- `models/`: esquemas y modelos de dominio.
- `flows/`: orquestación de conversación y transiciones.
- `routes/`: fronteras explícitas por contexto.
- `services/`: lógica de negocio y helpers reutilizables.
- `templates/`: copys, payloads y mensajes visibles para el usuario.
- `infrastructure/`: integración técnica con Redis, Supabase, OpenAI y storage.
- `principal.py`: punto de entrada de la aplicación.
- `utils/`: helpers puros y sin acoplamiento al flujo.
- `tools/`: scripts y procesos manuales de mantenimiento.
- `tests/`: validación automatizada.

## Contextos principales

### Onboarding

Alta inicial del proveedor, captura de datos y envío a revisión.

Rutas y piezas relevantes:

- `routes/onboarding/`
- `flows/onboarding/`
- `services/onboarding/`
- `templates/onboarding/`
- `templates/onboarding/registration/`

Política actual:

- el paso de servicios publica un evento crudo y no espera la normalización de IA en el request path
- `provider-onboarding-worker` consume el evento, llama al endpoint interno de `ai-proveedores` y persiste el resultado en Supabase
- `experience_range` es la única representación canónica de experiencia; `experience_years` ya no forma parte del contrato vivo

### Review

Estado de espera entre el alta y el uso operativo.

Rutas y piezas relevantes:

- `routes/review/`
- `services/review/`
- `templates/review/`

### Maintenance

Menú operativo del proveedor ya registrado.

Rutas y piezas relevantes:

- `routes/maintenance/`
- `flows/maintenance/`
- `services/maintenance/`
- `templates/maintenance/`

### Availability

Respuesta a disponibilidad del proveedor cuando existe una solicitud entrante.

Rutas y piezas relevantes:

- `routes/availability/`
- `services/availability/`

## Capas compartidas

### `services/shared/`

Contiene la normalización común de respuestas y los prompts compartidos de IA:

- `normalizacion_respuestas.py`
- `prompts_ia.py`

### `templates/shared/`

Contiene mensajes y copys transversales:

- mensajes de sesión
- mensajes de interacción
- mensajes comunes

## Reglas de organización

- `flows/` debe orquestar, no definir copy de usuario.
- `templates/` debe concentrar el texto visible.
- `services/shared/` debe concentrar reglas reutilizables de interacción.
- `infrastructure/` debe limitarse a integración técnica.
- `utils/` debe contener funciones puras y compartidas.
- `tools/` no forma parte del runtime; solo existe para operación manual o batch.

## Documentos de referencia

- [`FRONTERAS_FLUJO.md`](./FRONTERAS_FLUJO.md)
- [`FLUJO_SISTEMA.md`](./FLUJO_SISTEMA.md)
- [`tools/README.md`](./tools/README.md)

## Configuración clave

Variables y valores centralizados en `config/configuracion.py`:

- `openai_chat_model`
- `openai_temperature_precisa`
- `openai_temperature_consistente`
- `pais_operativo`
- `maximo_servicio_visible`

## Calidad y validación

Ejecuta la validación del servicio desde la raíz del repositorio:

```bash
python validate_quality.py --service ai-proveedores
```

Para una pasada completa del workspace:

```bash
./validate_all.sh
```

## Nota importante

`runtime` es un criterio arquitectónico del servicio, no una carpeta física obligatoria. La aplicación corre con las capas top-level ya existentes, y la separación se mantiene por responsabilidad, no por una reubicación artificial.
