-- Backfill 15: lote 03 de identidad documental de providers.
-- Regla aprobada:
-- - 2 tokens: 1er token = nombres, 2do token = apellidos
-- - 3 tokens: 1er y 2do token = nombres, 3er token = apellidos
-- - 4+ tokens: primeros 2 tokens = nombres, resto = apellidos
--
-- Excepciones manuales aprobadas para este lote:
-- - "Josue Damian Garcia Jimbo}" -> "Josue Damian" / "Garcia Jimbo"
-- - "Augusto Zhinin Matute" -> "Augusto" / "Zhinin Matute"
-- - "Benavides Godoy Jefferson Wilfrido" -> "Jefferson Wilfrido" / "Benavides Godoy"

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
  offset 20
  limit 10
),
partes as (
  select
    id,
    full_name,
    case
      when full_name = 'Josue Damian Garcia Jimbo}' then 'Josue Damian'
      when full_name = 'Augusto Zhinin Matute' then 'Augusto'
      when full_name = 'Benavides Godoy Jefferson Wilfrido' then 'Jefferson Wilfrido'
      when cardinality(name_tokens) = 1 then name_tokens[1]
      when cardinality(name_tokens) = 2 then name_tokens[1]
      when cardinality(name_tokens) = 3 then array_to_string(name_tokens[1:2], ' ')
      else array_to_string(name_tokens[1:2], ' ')
    end as proposed_document_first_names,
    case
      when full_name = 'Josue Damian Garcia Jimbo}' then 'Garcia Jimbo'
      when full_name = 'Augusto Zhinin Matute' then 'Zhinin Matute'
      when full_name = 'Benavides Godoy Jefferson Wilfrido' then 'Benavides Godoy'
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

