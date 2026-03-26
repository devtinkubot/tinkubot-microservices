-- Identidades WhatsApp por proveedor.
-- Permite resolver continuidad por phone, @lid o BSUID/user_id sin usar real_phone.

create table if not exists public.provider_whatsapp_identities (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references public.providers(id) on delete cascade,
  whatsapp_account_id text not null default '',
  identity_type text not null,
  identity_value text not null,
  is_primary boolean not null default false,
  first_seen_at timestamptz not null default timezone('utc'::text, now()),
  last_seen_at timestamptz not null default timezone('utc'::text, now()),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc'::text, now()),
  updated_at timestamptz not null default timezone('utc'::text, now()),
  constraint provider_whatsapp_identities_identity_type_check
    check (identity_type in ('phone', 'lid', 'user_id'))
);

create unique index if not exists provider_whatsapp_identities_unique_identity
  on public.provider_whatsapp_identities (
    whatsapp_account_id,
    identity_type,
    identity_value
  );

create index if not exists provider_whatsapp_identities_provider_idx
  on public.provider_whatsapp_identities (provider_id, is_primary desc, last_seen_at desc);

create index if not exists provider_whatsapp_identities_value_idx
  on public.provider_whatsapp_identities (identity_value);

alter table public.provider_whatsapp_identities enable row level security;
