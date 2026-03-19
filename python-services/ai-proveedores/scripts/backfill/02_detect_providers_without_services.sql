-- Backfill 2: Detectar proveedores con provider_services vacíos y reviews pendientes
-- Ejecutar en Supabase SQL Editor

-- Proveedores sin servicios pero con reviews pendientes
SELECT
    p.id as provider_id,
    p.phone,
    p.full_name,
    COUNT(r.id) as pending_reviews_count,
    array_agg(r.service_name) as pending_services
FROM providers p
JOIN provider_service_catalog_reviews r ON r.provider_id = p.id
WHERE p.id NOT IN (SELECT provider_id FROM provider_services WHERE provider_id IS NOT NULL)
AND r.review_status = 'pending'
GROUP BY p.id, p.phone, p.full_name
ORDER BY pending_reviews_count DESC;

-- Proveedores con reviews huérfanas que podrían ser vinculadas por phone pattern
SELECT
    p.id as provider_id,
    p.phone,
    p.full_name,
    COUNT(r.id) as orphan_reviews_count
FROM providers p
JOIN provider_service_catalog_reviews r
    ON r.raw_service_text ILIKE '%' || p.phone || '%'
    OR r.raw_service_text ~ ('.*' || substring(p.phone from '[0-9]{9,}') || '.*')
WHERE r.provider_id IS NULL
AND r.review_status = 'pending'
GROUP BY p.id, p.phone, p.full_name
ORDER BY orphan_reviews_count DESC;
