-- El campo phone ahora debe poder guardar identidad WhatsApp canónica:
-- número, @lid o BSUID en formato user_id.

alter table public.providers
  alter column phone type text
  using phone::text;

alter table public.providers
  alter column phone set not null;
