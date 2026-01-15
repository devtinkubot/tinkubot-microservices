-- ============================================================================
-- ÍNDICES ADICIONALES PARA BÚSQUEDA DE PROVEEDORES
-- Plan: Mejoras Inmediatas al Sistema de Búsqueda (Enero 2026)
-- ============================================================================

-- 1. Índice compuesto: city + profession + rating
CREATE INDEX IF NOT EXISTS idx_providers_city_profession_rating
ON providers(city, profession, rating DESC)
WHERE verified = true;

-- 2. Índice: verified + rating para ranking statewide
CREATE INDEX IF NOT EXISTS idx_providers_verified_rating
ON providers(verified, rating DESC)
WHERE verified = true;

-- 3. Actualizar estadísticas
ANALYZE providers;

-- 4. Verificación - Mostrar todos los índices de providers
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'providers'
  AND indexname IN (
    'idx_providers_city_profession_rating',
    'idx_providers_verified_rating'
  )
ORDER BY indexname;
