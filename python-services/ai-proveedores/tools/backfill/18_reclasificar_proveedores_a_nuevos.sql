-- Reclasificación manual de proveedores a la cola "Nuevos".
-- Objetivo:
-- - mover todos los casos a onboarding_step = pending_verification
-- - para los que estaban approved, además bajar status a pending y marcar onboarding_complete
--
-- Casos incluidos:
-- - 0b4e962e-2d2c-44e0-a704-1f53f56c0f96
-- - 5ae50a42-dad3-413e-b208-7cd0aacdb47e
-- - 1b5ba4eb-48ae-4b18-b169-2a17f45ece0b
-- - a0a9d9a1-4111-4c39-a24d-903e15e8e280
-- - 135708ab-dcb3-4c6e-8022-747ff4c6c26d
-- - 82a145a6-a3e1-4354-82db-de37eef561b8

with candidatos as (
  select
    id,
    status
  from public.providers
  where id in (
    '0b4e962e-2d2c-44e0-a704-1f53f56c0f96',
    '5ae50a42-dad3-413e-b208-7cd0aacdb47e',
    '1b5ba4eb-48ae-4b18-b169-2a17f45ece0b',
    'a0a9d9a1-4111-4c39-a24d-903e15e8e280',
    '135708ab-dcb3-4c6e-8022-747ff4c6c26d',
    '82a145a6-a3e1-4354-82db-de37eef561b8'
  )
)
update public.providers p
set
  onboarding_step = 'pending_verification',
  onboarding_step_updated_at = timezone('utc'::text, now()),
  onboarding_complete = true,
  status = case
    when candidatos.status = 'approved' then 'pending'
    else p.status
  end,
  updated_at = timezone('utc'::text, now())
from candidatos
where p.id = candidatos.id
returning
  p.id,
  p.full_name,
  p.status,
  p.onboarding_complete,
  p.onboarding_step,
  p.onboarding_step_updated_at;
