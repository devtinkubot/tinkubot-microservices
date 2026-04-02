-- Backfill 13: lote 01 de identidad documental de providers.
-- Regla aprobada:
-- - 2 tokens: 1er token = nombres, 2do token = apellidos
-- - 3 tokens: 1er y 2do token = nombres, 3er token = apellidos
-- - 4+ tokens: primeros 2 tokens = nombres, resto = apellidos
--
-- Este script actualiza solo los primeros 10 candidatos estables:
-- order by created_at asc nulls last, id asc
-- y solo cuando falta al menos uno de los campos documentales.

with candidatos as (
  select
    p.id,
    trim(p.full_name) as full_name,
    array_remove(regexp_split_to_array(trim(p.full_name), '\s+'), '') as name_tokens
  from public.providers p
  where coalesce(trim(p.full_name), '') <> ''
    and (
      coalesce(trim(p.document_first_names), '') = ''
      or coalesce(trim(p.document_last_names), '') = ''
    )
  order by p.created_at asc nulls last, p.id asc
  limit 10
),
partes as (
  select
    id,
    case
      when cardinality(name_tokens) = 1 then name_tokens[1]
      when cardinality(name_tokens) = 2 then name_tokens[1]
      when cardinality(name_tokens) = 3 then array_to_string(name_tokens[1:2], ' ')
      else array_to_string(name_tokens[1:2], ' ')
    end as proposed_document_first_names,
    case
      when cardinality(name_tokens) = 1 then null
      when cardinality(name_tokens) = 2 then name_tokens[2]
      when cardinality(name_tokens) = 3 then name_tokens[3]
      else array_to_string(name_tokens[3:cardinality(name_tokens)], ' ')
    end as proposed_document_last_names
  from candidatos
)
update public.providers p
set
  document_first_names = partes.proposed_document_first_names,
  document_last_names = partes.proposed_document_last_names
from partes
where p.id = partes.id
returning
  p.id,
  p.full_name,
  p.document_first_names,
  p.document_last_names;

-- Verificación sugerida:
-- select id, full_name, document_first_names, document_last_names
-- from public.providers
-- where id in (
--   select id
--   from public.providers
--   where coalesce(trim(full_name), '') <> ''
--     and (
--       coalesce(trim(document_first_names), '') = ''
--       or coalesce(trim(document_last_names), '') = ''
--     )
--   order by created_at asc nulls last, id asc
--   limit 10
-- )
-- order by created_at asc nulls last, id asc;
