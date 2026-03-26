-- Campos manuales de revisión administrativa para providers.
-- Se guardan los nombres leídos del documento y la cédula transcrita por el admin.

alter table public.providers
  add column if not exists document_first_names text null,
  add column if not exists document_last_names text null,
  add column if not exists document_id_number text null;

alter table public.providers
  add column if not exists display_name text null,
  add column if not exists formatted_name text null,
  add column if not exists first_name text null,
  add column if not exists last_name text null;

create index if not exists idx_providers_document_id_number
  on public.providers using btree (document_id_number);
