-- Backfill 17: lote 05 de identidad documental de providers.
-- Regla aprobada:
-- - 2 tokens: 1er token = nombres, 2do token = apellidos
-- - 3 tokens: 1er y 2do token = nombres, 3er token = apellidos
-- - 4+ tokens: primeros 2 tokens = nombres, resto = apellidos
--
-- Ajuste manual aprobado:
-- - "Juanpa Gallegos" -> "Juan Pablo" / "Gallegos"

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
    and p.id in (
      '3fe5480a-91c8-48d2-92e7-f365506cac77',
      '7d7bda6d-9ce2-4f80-af7d-311c51a14be1',
      '522c71ae-f19a-446f-a273-81cc57ecbdaf',
      'efe0415d-1adb-4809-8032-055ff7183097',
      '13414de5-008f-4c0a-a39b-1e7e8bc74b53',
      '4b5d7e9e-c0b4-4902-ad71-21f2cf236c8a',
      'e43a67bb-2ba5-4705-a808-4d26b16712c3'
    )
),
partes as (
  select
    id,
    full_name,
    case
      when full_name = 'Juanpa Gallegos' then 'Juan Pablo'
      when cardinality(name_tokens) = 1 then name_tokens[1]
      when cardinality(name_tokens) = 2 then name_tokens[1]
      when cardinality(name_tokens) = 3 then array_to_string(name_tokens[1:2], ' ')
      else array_to_string(name_tokens[1:2], ' ')
    end as proposed_document_first_names,
    case
      when full_name = 'Juanpa Gallegos' then 'Gallegos'
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

