-- Retira la columna legacy de experiencia numérica del contrato vivo.

alter table public.providers
  drop column if exists experience_years;
