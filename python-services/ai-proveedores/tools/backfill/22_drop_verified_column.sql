-- Elimina la columna `verified` de la tabla `providers`.
-- Ya no se usa en la logica de negocio; la verificacion real se basa en
-- `status = 'approved'` y `onboarding_complete`.

ALTER TABLE providers
  DROP COLUMN IF EXISTS verified;
