-- Registro mínimo de eventos de onboarding para proveedores
-- Guarda solo trazabilidad: aviso 48h y baja 72h.

create table if not exists public.provider_onboarding_lifecycle_events (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null,
  provider_phone text not null,
  provider_name text,
  event_type text not null,
  approved_basic_at timestamptz not null,
  event_at timestamptz not null default timezone('utc'::text, now()),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc'::text, now()),
  constraint provider_onboarding_lifecycle_events_event_type_check
    check (event_type in ('warning_48h', 'expired_72h'))
);

create unique index if not exists provider_onboarding_lifecycle_events_provider_event_type_key
  on public.provider_onboarding_lifecycle_events (provider_id, event_type);

create index if not exists provider_onboarding_lifecycle_events_event_type_idx
  on public.provider_onboarding_lifecycle_events (event_type, event_at desc);

create index if not exists provider_onboarding_lifecycle_events_provider_phone_idx
  on public.provider_onboarding_lifecycle_events (provider_phone);

alter table public.provider_onboarding_lifecycle_events enable row level security;
