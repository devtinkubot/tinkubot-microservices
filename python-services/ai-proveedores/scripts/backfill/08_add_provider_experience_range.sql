-- Campo derivado para rango legible de experiencia.
-- Se mantiene experience_years como fuente numérica y experience_range como texto.

alter table public.providers
  add column if not exists experience_range text null;

update public.providers
set experience_range = case
  when coalesce(experience_years, 0) < 1 then 'Menos de 1 año'
  when experience_years < 3 then '1 a 3 años'
  when experience_years < 5 then '3 a 5 años'
  when experience_years < 10 then '5 a 10 años'
  else 'Más de 10 años'
end
where experience_range is null;
