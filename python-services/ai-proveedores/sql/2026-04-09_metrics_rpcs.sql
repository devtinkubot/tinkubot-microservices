-- ============================================================
-- Métricas Operativas v1 — RPCs para KPIs de demanda
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- Índices recomendados
CREATE INDEX IF NOT EXISTS idx_service_requests_requested_at
  ON service_requests (requested_at);

CREATE INDEX IF NOT EXISTS idx_service_requests_city_requested
  ON service_requests (location_city, requested_at);

CREATE INDEX IF NOT EXISTS idx_service_requests_profession_requested
  ON service_requests (profession, requested_at);

CREATE INDEX IF NOT EXISTS idx_lead_events_created_at
  ON lead_events (created_at);

CREATE INDEX IF NOT EXISTS idx_lead_feedback_created_at
  ON lead_feedback (created_at);

CREATE INDEX IF NOT EXISTS idx_providers_status_onboarding
  ON providers (status, onboarding_complete);


-- ============================================================
-- RPC 1: Búsquedas por período (Tier 1 — KPI 1+5)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_searches_per_day(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW(),
  p_granularity TEXT DEFAULT 'day'
)
RETURNS TABLE(period TEXT, total_searches BIGINT, unique_searchers BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT
    TO_CHAR(DATE_TRUNC(p_granularity, requested_at), 'YYYY-MM-DD') AS period,
    COUNT(*)::BIGINT AS total_searches,
    COUNT(DISTINCT phone)::BIGINT AS unique_searchers
  FROM service_requests
  WHERE requested_at >= p_from
    AND requested_at < p_to
  GROUP BY DATE_TRUNC(p_granularity, requested_at)
  ORDER BY period;
$$;


-- ============================================================
-- RPC 2: Búsquedas por ciudad (Tier 1 — KPI 2)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_searches_by_city(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW(),
  p_limit INT DEFAULT 20
)
RETURNS TABLE(city TEXT, total_searches BIGINT, unique_searchers BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT
    COALESCE(LOWER(TRIM(location_city)), 'desconocido') AS city,
    COUNT(*)::BIGINT AS total_searches,
    COUNT(DISTINCT phone)::BIGINT AS unique_searchers
  FROM service_requests
  WHERE requested_at >= p_from
    AND requested_at < p_to
  GROUP BY COALESCE(LOWER(TRIM(location_city)), 'desconocido')
  ORDER BY total_searches DESC
  LIMIT p_limit;
$$;


-- ============================================================
-- RPC 3: Búsquedas por servicio (Tier 1 — KPI 3)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_searches_by_service(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW(),
  p_limit INT DEFAULT 20
)
RETURNS TABLE(service TEXT, total_searches BIGINT, unique_searchers BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT
    COALESCE(LOWER(TRIM(profession)), 'desconocido') AS service,
    COUNT(*)::BIGINT AS total_searches,
    COUNT(DISTINCT phone)::BIGINT AS unique_searchers
  FROM service_requests
  WHERE requested_at >= p_from
    AND requested_at < p_to
  GROUP BY COALESCE(LOWER(TRIM(profession)), 'desconocido')
  ORDER BY total_searches DESC
  LIMIT p_limit;
$$;


-- ============================================================
-- RPC 4: Conversión búsqueda → lead (Tier 1 — KPI 4)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_search_to_lead_conversion(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE(
  total_searches BIGINT,
  total_leads BIGINT,
  conversion_rate NUMERIC
)
LANGUAGE sql STABLE
AS $$
  SELECT
    (SELECT COUNT(*)::BIGINT FROM service_requests
     WHERE requested_at >= p_from AND requested_at < p_to) AS total_searches,
    (SELECT COUNT(*)::BIGINT FROM lead_events
     WHERE created_at >= p_from AND created_at < p_to) AS total_leads,
    CASE
      WHEN (SELECT COUNT(*) FROM service_requests
            WHERE requested_at >= p_from AND requested_at < p_to) = 0 THEN 0
      ELSE ROUND(
        (SELECT COUNT(*)::NUMERIC FROM lead_events
         WHERE created_at >= p_from AND created_at < p_to)
        /
        (SELECT COUNT(*)::NUMERIC FROM service_requests
         WHERE requested_at >= p_from AND requested_at < p_to),
        4
      )
    END AS conversion_rate;
$$;


-- ============================================================
-- RPC 5: Horas pico (Tier 1 — KPI 6)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_peak_hours(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE(hour_of_day INT, total_searches BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT
    EXTRACT(HOUR FROM requested_at AT TIME ZONE 'America/Guayaquil')::INT AS hour_of_day,
    COUNT(*)::BIGINT AS total_searches
  FROM service_requests
  WHERE requested_at >= p_from
    AND requested_at < p_to
  GROUP BY hour_of_day
  ORDER BY hour_of_day;
$$;


-- ============================================================
-- RPC 6: Oferta por ciudad y servicio (Tier 2 — KPI 7)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_supply_by_city_service(
  p_limit INT DEFAULT 30
)
RETURNS TABLE(city TEXT, service_name TEXT, provider_count BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT
    COALESCE(LOWER(TRIM(p.city)), 'desconocido') AS city,
    COALESCE(LOWER(TRIM(ps.service_name)), 'desconocido') AS service_name,
    COUNT(DISTINCT p.id)::BIGINT AS provider_count
  FROM providers p
  JOIN provider_services ps ON ps.provider_id = p.id
  WHERE p.onboarding_complete = TRUE
  GROUP BY COALESCE(LOWER(TRIM(p.city)), 'desconocido'),
           COALESCE(LOWER(TRIM(ps.service_name)), 'desconocido')
  ORDER BY provider_count DESC
  LIMIT p_limit;
$$;


-- ============================================================
-- RPC 7: Completitud de onboarding (Tier 2 — KPI 8)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_onboarding_completion(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE(
  total_started BIGINT,
  total_completed BIGINT,
  completion_rate NUMERIC
)
LANGUAGE sql STABLE
AS $$
  SELECT
    (SELECT COUNT(*)::BIGINT FROM providers
     WHERE created_at >= p_from AND created_at < p_to) AS total_started,
    (SELECT COUNT(*)::BIGINT FROM providers
     WHERE created_at >= p_from AND created_at < p_to
       AND onboarding_complete = TRUE) AS total_completed,
    CASE
      WHEN (SELECT COUNT(*) FROM providers
            WHERE created_at >= p_from AND created_at < p_to) = 0 THEN 0
      ELSE ROUND(
        (SELECT COUNT(*)::NUMERIC FROM providers
         WHERE created_at >= p_from AND created_at < p_to
           AND onboarding_complete = TRUE)
        /
        (SELECT COUNT(*)::NUMERIC FROM providers
         WHERE created_at >= p_from AND created_at < p_to),
        4
      )
    END AS completion_rate;
$$;


-- ============================================================
-- RPC 8: Calidad de contratación (Tier 3 — KPI 10+11)
-- ============================================================
CREATE OR REPLACE FUNCTION metrics_hiring_quality(
  p_from TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
  p_to   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE(
  total_feedback BIGINT,
  total_hired BIGINT,
  hiring_rate NUMERIC,
  avg_rating NUMERIC
)
LANGUAGE sql STABLE
AS $$
  SELECT
    COUNT(*)::BIGINT AS total_feedback,
    COUNT(*) FILTER (WHERE hired = TRUE)::BIGINT AS total_hired,
    CASE
      WHEN COUNT(*) = 0 THEN 0
      ELSE ROUND(COUNT(*) FILTER (WHERE hired = TRUE)::NUMERIC / COUNT(*)::NUMERIC, 4)
    END AS hiring_rate,
    ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL), 2) AS avg_rating
  FROM lead_feedback
  WHERE created_at >= p_from
    AND created_at < p_to;
$$;
