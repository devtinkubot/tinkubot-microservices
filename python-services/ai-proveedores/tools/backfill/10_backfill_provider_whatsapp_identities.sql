-- Backfill de identidades WhatsApp para proveedores existentes.
-- Poblamos la identidad principal desde `providers.phone` y, si existe,
-- una identidad secundaria desde `providers.real_phone`.

with raw_identities as (
  select
    p.id as provider_id,
    ''::text as whatsapp_account_id,
    case
      when p.phone ilike '%@lid' then 'lid'
      else 'phone'
    end as identity_type,
    trim(p.phone)::text as identity_value,
    true as is_primary,
    coalesce(p.created_at, timezone('utc'::text, now())) as first_seen_at,
    timezone('utc'::text, now()) as last_seen_at,
    jsonb_build_object('source', 'backfill', 'field', 'phone') as metadata,
    1 as priority
  from public.providers p
  where coalesce(trim(p.phone), '') <> ''

  union all

  select
    p.id as provider_id,
    ''::text as whatsapp_account_id,
    case
      when coalesce(p.real_phone, '') like '%@lid' then 'lid'
      when coalesce(p.real_phone, '') like '%@%' then 'phone'
      else 'phone'
    end as identity_type,
    case
      when coalesce(p.real_phone, '') like '%@%' then trim(p.real_phone)
      else regexp_replace(coalesce(p.real_phone, ''), '\D', '', 'g') || '@s.whatsapp.net'
    end as identity_value,
    false as is_primary,
    coalesce(p.created_at, timezone('utc'::text, now())) as first_seen_at,
    timezone('utc'::text, now()) as last_seen_at,
    jsonb_build_object('source', 'backfill', 'field', 'real_phone') as metadata,
    2 as priority
  from public.providers p
  where coalesce(trim(p.real_phone), '') <> ''
),
deduped as (
  select distinct on (whatsapp_account_id, identity_type, identity_value)
    provider_id,
    whatsapp_account_id,
    identity_type,
    identity_value,
    is_primary,
    first_seen_at,
    last_seen_at,
    metadata
  from raw_identities
  where coalesce(trim(identity_value), '') <> ''
  order by whatsapp_account_id, identity_type, identity_value, priority asc, is_primary desc, last_seen_at desc
)
insert into public.provider_whatsapp_identities (
  provider_id,
  whatsapp_account_id,
  identity_type,
  identity_value,
  is_primary,
  first_seen_at,
  last_seen_at,
  metadata
)
select
  provider_id,
  whatsapp_account_id,
  identity_type,
  identity_value,
  is_primary,
  first_seen_at,
  last_seen_at,
  metadata
from deduped
on conflict (whatsapp_account_id, identity_type, identity_value)
do update set
  provider_id = excluded.provider_id,
  is_primary = excluded.is_primary,
  last_seen_at = excluded.last_seen_at,
  updated_at = excluded.updated_at,
  metadata = excluded.metadata;
