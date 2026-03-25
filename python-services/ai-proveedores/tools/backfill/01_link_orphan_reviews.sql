-- Backfill 1: Vincular reviews huérfanas a proveedores por teléfono
-- Ejecutar en Supabase SQL Editor

-- Paso 1: Detectar reviews con provider_id null que pueden ser vinculadas
SELECT
    r.id as review_id,
    r.service_name,
    r.raw_service_text,
    r.suggested_domain_code,
    r.review_status,
    p.id as matched_provider_id,
    p.phone as provider_phone,
    p.full_name as provider_name
FROM provider_service_catalog_reviews r
JOIN providers p ON p.phone LIKE '%' || substring(r.raw_service_text from '[0-9]{9,}') || '%'
    OR r.raw_service_text ILIKE '%' || p.phone || '%'
WHERE r.provider_id IS NULL
AND r.review_status = 'pending'
LIMIT 100;

-- Paso 2: Actualizar provider_id en reviews huérfanas (descomentar para ejecutar)
-- UPDATE provider_service_catalog_reviews r
-- SET provider_id = p.id
-- FROM providers p
-- WHERE r.provider_id IS NULL
-- AND r.review_status = 'pending'
-- AND (
--     p.phone LIKE '%' || substring(r.raw_service_text from '[0-9]{9,}') || '%'
--     OR r.raw_service_text ILIKE '%' || p.phone || '%'
-- );
