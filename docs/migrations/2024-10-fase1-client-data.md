# Fase 1 – Modelo de Datos (Clientes)

Este documento complementa `docs/customer-experience-plan.md` y describe la implementación técnica de la Fase 1.

## Objetivo
Separar el registro de clientes del resto de usuarios y habilitar una tabla dedicada para las solicitudes de servicio, manteniendo el histórico existente en Supabase.

## Archivos creados
- `supabase/migrations/20241031120000_create_customers_schema.sql`
  - Crea `public.customers`, `public.customer_service_requests`, índices y un trigger `handle_updated_at` para mantener `updated_at`.
- `supabase/migrations/20241031121000_backfill_customers_data.sql`
  - Copia los usuarios con `user_type = 'client'` hacia `public.customers` y migra los registros de `public.service_requests` al nuevo historial.

## Ejecución sugerida
1. **Backup**: generar un dump puntual de `public.users` y `public.service_requests`.
2. **Aplicar schema**:
   ```bash
   supabase db execute --file supabase/migrations/20241031120000_create_customers_schema.sql
   ```
3. **Backfill**:
   ```bash
   supabase db execute --file supabase/migrations/20241031121000_backfill_customers_data.sql
   ```
4. **Verificación**:
   - `select count(*) from public.customers;`
   - `select count(*) from public.customer_service_requests;`
   - Validar que `phone_number` permanece único en `customers`.

> Nota: el `UPDATE` para marcar usuarios como `legacy_client` queda comentado en el backfill hasta que el backend consuma la nueva tabla.

## Plan de rollback
Si algo falla, ejecutar en orden inverso dentro de una transacción:

```sql
BEGIN;
DELETE FROM public.customer_service_requests;
DROP TABLE IF EXISTS public.customer_service_requests;
DROP TRIGGER IF EXISTS trg_customers_set_updated_at ON public.customers;
DROP FUNCTION IF EXISTS public.handle_updated_at();
DROP TABLE IF EXISTS public.customers;
COMMIT;
```

Para revertir solo el backfill sin tocar el esquema, borrar el contenido:

```sql
BEGIN;
DELETE FROM public.customer_service_requests;
DELETE FROM public.customers;
COMMIT;
```

Tras el rollback, restaurar `public.users` y `public.service_requests` desde el backup si se alteraron manualmente.

## Próximos pasos
- Ajustar los servicios Python para leer/escribir en `public.customers` (Fase 2).
- Activar la marca `legacy_client` cuando el backend deje de depender de `public.users`.
