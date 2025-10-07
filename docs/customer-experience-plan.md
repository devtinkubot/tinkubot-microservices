# Plan de Refactorización: Gestión de Cliente y Ubicación en AI Service Clientes

## Objetivo General
Separar datos de clientes vs. proveedores, reducir fricción al pedir ciudad, y habilitar trazabilidad de solicitudes utilizando Supabase como fuente de verdad.

---

## Fase 1 – Modelo de Datos
- **1.1 Creación de tablas**
  - `customers`: `id uuid`, `phone_number text unique`, `full_name text`, `city text`, `city_confirmed_at timestamptz`, `notes jsonb`, `created_at`, `updated_at`.
  - `customer_service_requests`: `id uuid`, `customer_id uuid references customers`, `profession_id uuid` (nullable), `profession_name text`, `city_snapshot text`, `urgency text`, `status text`, `requested_at`, `resolved_at`, `provider_id uuid` (nullable), `metadata jsonb`.
- **1.2 Migración de datos**
  - Extraer filas de `users` con `user_type='client'` a `customers` y eliminarlas/al marcarlas como legacy.
  - Popular `customer_service_requests` con datos existentes de `service_requests` (opcional inicial) para mantener histórico.
- **1.3 Rollback plan**
  - Scripts inversos o estrategias de backup antes de migrar.

## Fase 2 – Backend (ai-service-clientes)
- **2.1 Adaptar acceso a Supabase**
  - Reemplazar `supabase_find_or_create_user` por helper `get_or_create_customer` que consulte `customers` por teléfono.
- **2.2 Gestión de ciudad y flujo**
  - Al detectar opción “puedo esperar”: si `customers.city` existe, pedir confirmación “Seguimos buscando en <city>?”.
  - Si confirma, usarla; si niega o no existe, preguntar ciudad manualmente.
  - Para “urgente”: solicitar ubicación con coordenadas y guardar `city_snapshot` como `None` o derivar si el flujo la envía luego.
  - Cuando el usuario provea ciudad distinta, actualizar `customers.city` + `city_confirmed_at`.
- **2.3 Registro de solicitudes**
  - Al concretar la búsqueda, insertar en `customer_service_requests` (mantener `service_requests` vigente mientras tanto si necesario).

## Fase 3 – Observabilidad y UX
- **3.1 Logging**
  - Añadir logs claros cuando recuperamos ciudad previa, cuando el cliente la actualiza y cuando falla Supabase.
- **3.2 Experiencia de usuario**
  - Ajustar prompts para explicar por qué pedimos ciudad/ubicación según el caso.
  - Ofrecer alternativa manual (“puedes escribir otra ciudad si cambiaste”).
- **3.3 Documentación**
  - Actualizar README/diagramas de flujo con el nuevo comportamiento.

## Fase 4 – Extensiones Futuras (Opcional)
- Persistir resúmenes de conversación (tabla `customer_engagements`).
- Explorar uso de `metadata jsonb` para guardar preferencia de contacto, historial y feedbacks.
- Analítica: dashboard básico de ciudades y solicitudes recurrentes.

---

_Listo para iniciar mañana._

## Recursos Técnicos
- Fase 1: ver `docs/migrations/2024-10-fase1-client-data.md` para detalles de migración y rollback.
