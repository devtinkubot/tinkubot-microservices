-- Checkpoint duradero para reanudar onboarding sin depender solo de Redis.

alter table public.providers
  add column if not exists onboarding_step text null;

alter table public.providers
  add column if not exists onboarding_step_updated_at timestamptz null;
