-- Backfill 4: Vistas de lectura con timestamps normalizados a Ecuador
-- Ejecutar en Supabase SQL Editor
--
-- Objetivo:
-- - Mantener almacenamiento en UTC
-- - Exponer vistas de lectura con timestamps en hora local de Ecuador
-- - Evitar ambigüedad en frontend y consumidores de REST

create or replace view provider_service_catalog_reviews_ec as
select
    id,
    provider_id,
    raw_service_text,
    service_name,
    service_name_normalized,
    suggested_domain_code,
    proposed_category_name,
    proposed_service_summary,
    assigned_domain_code,
    assigned_category_name,
    assigned_service_name,
    assigned_service_summary,
    review_reason,
    review_status,
    source,
    reviewed_by,
    reviewed_at,
    review_notes,
    created_at,
    updated_at,
    published_provider_service_id,
    to_char(created_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as created_at_ec,
    to_char(updated_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as updated_at_ec,
    to_char(reviewed_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as reviewed_at_ec
from provider_service_catalog_reviews;

comment on view provider_service_catalog_reviews_ec is
    'Vista de lectura para reviews de gobernanza con columnas auxiliares en hora de Ecuador.';

create or replace view providers_ec as
select
    id,
    full_name,
    phone,
    real_phone,
    status,
    created_at,
    approved_notified_at,
    verification_reviewed_at,
    to_char(created_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as created_at_ec,
    to_char(approved_notified_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as approved_notified_at_ec,
    to_char(verification_reviewed_at at time zone 'America/Guayaquil', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
        || '-05:00' as verification_reviewed_at_ec
from providers;

comment on view providers_ec is
    'Vista de lectura para proveedores con timestamps auxiliares en hora de Ecuador.';
