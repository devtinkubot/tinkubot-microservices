-- Backfill 16: lote 04 de identidad documental de providers.
-- Regla aprobada:
-- - 2 tokens: 1er token = nombres, 2do token = apellidos
-- - 3 tokens: 1er y 2do token = nombres, 3er token = apellidos
-- - 4+ tokens: primeros 2 tokens = nombres, resto = apellidos
--
-- Este lote sólo contiene personas naturales.

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
      '00fcbdbb-dded-4343-a256-ae665947d701',
      '60aa4353-c2c1-426a-9aeb-90f90822605f',
      '28ed3388-ddc9-4b36-b66d-864dcc7c8ba3',
      '3c320080-b7da-4505-8cec-1738713e36e9',
      'c504ad52-4e8d-443d-9956-e567c7b1a3d9',
      'b842f872-89f9-4ec5-b1e7-bb52099fd8bc',
      '9851439c-c889-41e7-8191-ab920b603c4e',
      '88bb525e-b375-4296-8de3-fa4b51b2beea',
      '7f13d290-c50c-422e-8c4b-e8079c067bd9',
      'f31745b7-7a45-4d25-8693-b7dedc97cd43'
    )
),
partes as (
  select
    id,
    full_name,
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

