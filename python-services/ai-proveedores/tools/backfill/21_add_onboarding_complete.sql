-- Agrega la columna canónica para distinguir completitud del onboarding
-- de la aprobación administrativa.
--
-- `onboarding_complete` marca que el proceso humano-sistema terminó
-- y el proveedor quedó listo para revisión.
-- Se backfill-ea desde checkpoints finales o señales históricas de
-- proveedores ya completados.

BEGIN;

ALTER TABLE public.providers
  ADD COLUMN IF NOT EXISTS onboarding_complete boolean NOT NULL DEFAULT false;

UPDATE public.providers
SET onboarding_complete = true
WHERE onboarding_step IN (
  'pending_verification',
  'awaiting_menu_option'
)
OR status = 'approved'
OR verified = true;

COMMIT;
