-- Corrige la funcion rpc usada por ai-search:
-- 1. Reemplaza experience_years (columna eliminada) por experience_range
-- 2. Agrega campos de nombre: document_first_names, document_last_names,
--    display_name, formatted_name, first_name, last_name
-- 3. Construye social_media_url/social_media_type desde facebook_username/
--    instagram_username (las columnas que el onboarding realmente llena)

CREATE OR REPLACE FUNCTION public.match_provider_services(
    query_embedding vector,
    match_count integer,
    city_filter text DEFAULT NULL,
    similarity_threshold real DEFAULT 0.0
)
RETURNS TABLE(
    provider_id uuid,
    distance real,
    phone text,
    real_phone text,
    full_name text,
    city text,
    rating double precision,
    experience_range text,
    document_first_names text,
    document_last_names text,
    display_name text,
    social_media_url text,
    social_media_type text,
    face_photo_url text,
    created_at timestamp with time zone,
    services text[],
    service_summaries text[],
    matched_service_name text,
    matched_service_summary text,
    domain_code text,
    category_name text,
    classification_confidence real
)
LANGUAGE sql
STABLE
AS $function$
    WITH ranked_matches AS (
        SELECT
            p.id AS provider_id,
            p.phone,
            p.real_phone,
            p.full_name,
            p.city,
            p.rating,
            p.experience_range,
            p.document_first_names,
            p.document_last_names,
            p.display_name,
            CASE
                WHEN p.instagram_username IS NOT NULL AND p.instagram_username <> ''
                    THEN 'https://instagram.com/' || p.instagram_username
                WHEN p.facebook_username IS NOT NULL AND p.facebook_username <> ''
                    THEN 'https://facebook.com/' || p.facebook_username
                ELSE NULL
            END AS social_media_url,
            CASE
                WHEN p.instagram_username IS NOT NULL AND p.instagram_username <> ''
                    THEN 'Instagram'
                WHEN p.facebook_username IS NOT NULL AND p.facebook_username <> ''
                    THEN 'Facebook'
                ELSE NULL
            END AS social_media_type,
            p.face_photo_url,
            p.created_at,
            ps.service_name,
            ps.service_summary,
            ps.display_order,
            ps.domain_code,
            ps.category_name,
            ps.classification_confidence,
            (ps.service_embedding <=> query_embedding) AS distance,
            row_number() OVER (
                PARTITION BY p.id
                ORDER BY (ps.service_embedding <=> query_embedding), ps.display_order
            ) AS semantic_rank
        FROM provider_services ps
        JOIN providers p ON p.id = ps.provider_id
        WHERE ps.service_embedding IS NOT NULL
          AND p.status = 'approved'
          AND p.onboarding_complete = true
          AND (city_filter IS NULL OR p.city ILIKE city_filter)
    ),
    provider_services_agg AS (
        SELECT
            provider_id,
            array_agg(service_name ORDER BY display_order) AS services,
            array_agg(service_summary ORDER BY display_order) AS service_summaries
        FROM ranked_matches
        GROUP BY provider_id
    )
    SELECT
        rm.provider_id,
        rm.distance::real AS distance,
        rm.phone,
        rm.real_phone,
        rm.full_name,
        rm.city,
        rm.rating,
        rm.experience_range,
        rm.document_first_names,
        rm.document_last_names,
        rm.display_name,
        rm.social_media_url,
        rm.social_media_type,
        rm.face_photo_url,
        rm.created_at,
        psa.services,
        psa.service_summaries,
        rm.service_name AS matched_service_name,
        rm.service_summary AS matched_service_summary,
        rm.domain_code,
        rm.category_name,
        rm.classification_confidence
    FROM ranked_matches rm
    JOIN provider_services_agg psa
      ON psa.provider_id = rm.provider_id
    WHERE rm.semantic_rank = 1
      AND 1 - rm.distance >= similarity_threshold
    ORDER BY rm.distance ASC
    LIMIT match_count;
$function$;
