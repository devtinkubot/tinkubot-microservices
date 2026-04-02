-- Normalización idempotente de estados de proveedores.
--
-- Este backfill deja a Supabase en la terna canónica actual:
--   status: pending | approved | rejected
-- y corrige checkpoints legacy de onboarding a su forma estable.

BEGIN;

ALTER TABLE public.providers
  DROP CONSTRAINT IF EXISTS providers_status_check;

UPDATE public.providers
SET status = 'approved'
WHERE status IN (
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
  'aprobado'
);

UPDATE public.providers
SET status = 'pending'
WHERE status IN (
  'pendiente',
  'new'
);

UPDATE public.providers
SET status = 'rejected'
WHERE status IN (
  'rechazado',
  'denied'
);

UPDATE public.providers
SET
  onboarding_complete = true,
  onboarding_step = 'pending_verification',
  onboarding_step_updated_at = timezone('utc'::text, now()),
  updated_at = timezone('utc'::text, now())
WHERE status = 'pending'
  AND verified = true;

UPDATE public.providers
SET onboarding_step = CASE onboarding_step
  WHEN 'awaiting_city' THEN 'onboarding_city'
  WHEN 'awaiting_dni_front_photo' THEN 'onboarding_dni_front_photo'
  WHEN 'awaiting_face_photo' THEN 'onboarding_face_photo'
  WHEN 'awaiting_experience' THEN 'onboarding_experience'
  WHEN 'awaiting_specialty' THEN 'onboarding_specialty'
  WHEN 'awaiting_add_another_service' THEN 'onboarding_add_another_service'
  WHEN 'awaiting_social_media' THEN 'onboarding_social_media'
  WHEN 'awaiting_real_phone' THEN 'onboarding_real_phone'
  ELSE onboarding_step
END
WHERE onboarding_step IN (
  'awaiting_city',
  'awaiting_dni_front_photo',
  'awaiting_face_photo',
  'awaiting_experience',
  'awaiting_specialty',
  'awaiting_add_another_service',
  'awaiting_social_media',
  'awaiting_real_phone'
);

ALTER TABLE public.providers
  ADD CONSTRAINT providers_status_check
  CHECK (
    status = ANY (
      ARRAY[
        'pending'::text,
        'approved'::text,
        'rejected'::text
      ]
    )
  );

COMMIT;
