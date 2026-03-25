-- Elimina estados de verificación legacy del esquema de providers.
-- El flujo operativo real solo conserva: pending, approved y rejected.

ALTER TABLE public.providers
  DROP CONSTRAINT IF EXISTS providers_status_check;

UPDATE public.providers
SET status = 'approved'
WHERE status IN (
  'approved_basic',
  'profile_pending_review',
  'interview_required',
  'needs_info',
  'perfil_pendiente_revision',
  'professional_review_pending',
  'entrevista',
  'auditoria',
  'falta_info',
  'faltainfo'
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
