-- Permite marcar reviews de gobernanza como `enriched` cuando se asigna
-- dominio/categoría sin poder publicar un provider_service por falta de
-- provider_id.

ALTER TABLE provider_service_catalog_reviews
  DROP CONSTRAINT IF EXISTS provider_service_catalog_reviews_review_status_check;

ALTER TABLE provider_service_catalog_reviews
  ADD CONSTRAINT provider_service_catalog_reviews_review_status_check
  CHECK (
    review_status = ANY (
      ARRAY[
        'pending'::text,
        'approved_existing_domain'::text,
        'approved_new_domain'::text,
        'rejected'::text,
        'enriched'::text
      ]
    )
  );
