-- Backfills data into the new customer-centric tables preserving existing history.
BEGIN;

-- Copy current client users into the new customers table.
INSERT INTO public.customers AS c (
    id,
    phone_number,
    full_name,
    city
)
SELECT
    u.id,
    u.phone_number,
    NULLIF(u.name, '') AS full_name,
    u.city
FROM public.users u
WHERE u.user_type = 'client'
ON CONFLICT (id) DO UPDATE
SET
    phone_number = EXCLUDED.phone_number,
    full_name = EXCLUDED.full_name,
    city = EXCLUDED.city,
    updated_at = timezone('utc', now());

-- Preserve historical service requests with a link to the customer record.
WITH migrated AS (
    INSERT INTO public.customer_service_requests (
        id,
        customer_id,
        profession_id,
        profession_name,
        city_snapshot,
        urgency,
        status,
        requested_at,
        resolved_at,
        provider_id,
        metadata
    )
    SELECT
        sr.id,
        c.id,
        NULL::integer,
        sr.profession,
        sr.location_city,
        'unknown',
        CASE
            WHEN NULLIF(sr.resolved_at::text, '') IS NOT NULL THEN 'resolved'
            ELSE 'pending'
        END,
        COALESCE(NULLIF(sr.requested_at::text, '')::timestamptz, timezone('utc', now())),
        NULLIF(sr.resolved_at::text, '')::timestamptz,
        NULL::uuid,
        jsonb_build_object(
            'legacy_service_request', row_to_json(sr)::jsonb
        )
    FROM public.service_requests sr
    JOIN public.customers c ON c.phone_number = sr.phone
    WHERE NOT EXISTS (
        SELECT 1 FROM public.customer_service_requests csr WHERE csr.id = sr.id
    )
    RETURNING id
)
SELECT COUNT(*) AS inserted_customer_service_requests FROM migrated;

-- NOTE: When the application stops depending on client rows in public.users,
--       run the statement below (separately) to flag legacy records.
-- UPDATE public.users SET user_type = 'legacy_client' WHERE user_type = 'client';

COMMIT;
