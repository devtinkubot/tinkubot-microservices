-- Backfill 3: Reporte de reviews no resolubles automáticamente
-- Ejecutar en Supabase SQL Editor

-- Reviews pendientes sin provider_id y sin match telefónico
-- Estas requieren revisión manual
SELECT
    r.id,
    r.service_name,
    r.raw_service_text,
    r.suggested_domain_code,
    r.source,
    r.created_at,
    r.review_status
FROM provider_service_catalog_reviews r
WHERE r.provider_id IS NULL
AND r.review_status = 'pending'
AND NOT EXISTS (
    SELECT 1 FROM providers p
    WHERE p.phone LIKE '%' || substring(r.raw_service_text from '[0-9]{9,}') || '%'
    OR r.raw_service_text ILIKE '%' || p.phone || '%'
)
ORDER BY r.created_at DESC;

-- Opcionalmente, marcar como orphaned_pending_review para revisión manual
-- UPDATE provider_service_catalog_reviews
-- SET review_status = 'orphaned_pending_review',
--     review_notes = 'No se pudo vincular automáticamente a ningún proveedor'
-- WHERE provider_id IS NULL
-- AND review_status = 'pending'
-- AND NOT EXISTS (
--     SELECT 1 FROM providers p
--     WHERE p.phone LIKE '%' || substring(raw_service_text from '[0-9]{9,}') || '%'
--     OR raw_service_text ILIKE '%' || p.phone || '%'
-- );

-- Estadísticas de reviews
SELECT
    review_status,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE provider_id IS NOT NULL) as with_provider,
    COUNT(*) FILTER (WHERE provider_id IS NULL) as without_provider
FROM provider_service_catalog_reviews
GROUP BY review_status
ORDER BY count DESC;
