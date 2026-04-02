-- Auditoría de estados de proveedores.
--
-- No modifica datos. Sirve para detectar:
-- - estados legacy todavía persistidos
-- - checkpoints de onboarding fuera de la taxonomía actual
-- - inconsistencias entre status, verified, onboarding_complete y onboarding_step

select
  status,
  verified,
  onboarding_complete,
  onboarding_step,
  count(*) as count
from public.providers
group by status, verified, onboarding_complete, onboarding_step
order by count desc, status asc nulls first, onboarding_step asc nulls first;

select
  id,
  status,
  verified,
  onboarding_complete,
  onboarding_step,
  updated_at
from public.providers
where
  status in (
    'approved_basic',
    'aprobado_basico',
    'basic_approved',
    'perfil_pendiente_revision',
    'professional_review_pending',
    'interview_required',
    'entrevista',
    'auditoria',
    'needs_info',
    'falta_info',
    'faltainfo',
    'ok',
    'aprobado',
    'pendiente',
    'new',
    'rechazado',
    'denied'
  )
  or onboarding_step in (
    'awaiting_city',
    'awaiting_dni_front_photo',
    'awaiting_face_photo',
    'awaiting_experience',
    'awaiting_specialty',
    'awaiting_add_another_service',
    'awaiting_social_media',
    'awaiting_real_phone'
  )
  or (
    status = 'pending'
    and (verified = true or onboarding_complete = true)
  )
order by updated_at desc nulls last
limit 500;

select
  count(*) as pending_needs_review
from public.providers
where status = 'pending'
  and (verified = true or onboarding_complete = true);
