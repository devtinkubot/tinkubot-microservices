-- Campos manuales de revisión administrativa para providers.
-- Se guardan los nombres leídos del documento y la cédula transcrita por el admin.

alter table public.providers
  add column if not exists document_first_names text null,
  add column if not exists document_last_names text null,
  add column if not exists document_id_number text null;

create index if not exists idx_providers_document_id_number
  on public.providers using btree (document_id_number);

