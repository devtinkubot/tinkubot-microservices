-- Creates dedicated tables to manage client data and service request tracking.
-- Run inside Supabase/Postgres (transactional) to ensure atomicity.
BEGIN;

-- Ensure pgcrypto extension is available for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Helper function to auto-update the updated_at column
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Core customer registry
CREATE TABLE IF NOT EXISTS public.customers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number text NOT NULL,
    full_name text,
    city text,
    city_confirmed_at timestamptz,
    notes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT customers_phone_number_key UNIQUE (phone_number)
);

CREATE TRIGGER trg_customers_set_updated_at
BEFORE UPDATE ON public.customers
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Service request audit trail linked to customers
CREATE TABLE IF NOT EXISTS public.customer_service_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    profession_id integer REFERENCES public.professions(id) ON DELETE SET NULL,
    profession_name text,
    city_snapshot text,
    urgency text NOT NULL DEFAULT 'unknown',
    status text NOT NULL DEFAULT 'pending',
    requested_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    resolved_at timestamptz,
    provider_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Accelerate common lookup patterns
CREATE INDEX IF NOT EXISTS idx_customers_phone_number ON public.customers USING btree (phone_number);
CREATE INDEX IF NOT EXISTS idx_customer_service_requests_customer ON public.customer_service_requests USING btree (customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_service_requests_requested_at ON public.customer_service_requests USING btree (requested_at);

COMMIT;
