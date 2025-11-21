-- Esquema de base de datos optimizado para Search Service
-- PostgreSQL con índices especializados para búsqueda ultra-rápida

-- ========================================
-- 1. Tabla de Índice de Búsqueda de Proveedores
-- ========================================

CREATE TABLE IF NOT EXISTS provider_search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,

    -- Tokens normalizados para búsqueda
    profession_tokens TEXT[] NOT NULL,
    service_tokens TEXT[] NOT NULL,
    city_normalized VARCHAR(100),
    keywords TEXT[] NOT NULL,

    -- Vector de búsqueda full-text (PostgreSQL)
    search_vector tsvector,

    -- Metadatos
    provider_data JSONB NOT NULL, -- Datos cacheados del proveedor
    confidence_score FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_searched_at TIMESTAMP WITH TIME ZONE
);

-- ========================================
-- 2. Índices Especializados (CRÍTICOS PARA PERFORMANCE)
-- ========================================

-- Índice GIN para arrays de tokens (búsqueda por contención)
CREATE INDEX idx_provider_search_index_profession_tokens_gin
ON provider_search_index USING GIN(profession_tokens);

CREATE INDEX idx_provider_search_index_service_tokens_gin
ON provider_search_index USING GIN(service_tokens);

CREATE INDEX idx_provider_search_index_keywords_gin
ON provider_search_index USING GIN(keywords);

-- Índice GIN para búsqueda full-text (tsvector)
CREATE INDEX idx_provider_search_index_search_vector_gin
ON provider_search_index USING GIN(search_vector);

-- Índice B-tree para ciudad normalizada
CREATE INDEX idx_provider_search_index_city_normalized
ON provider_search_index(city_normalized) WHERE city_normalized IS NOT NULL;

-- Índices compuestos para consultas comunes
CREATE INDEX idx_provider_search_index_city_active
ON provider_search_index(city_normalized, is_active)
WHERE city_normalized IS NOT NULL AND is_active = true;

-- Índice para provider_id (referencias rápidas)
CREATE INDEX idx_provider_search_index_provider_id
ON provider_search_index(provider_id);

-- Índice para actualizaciones recientes
CREATE INDEX idx_provider_search_index_updated_at
ON provider_search_index(updated_at DESC);

-- ========================================
-- 3. Trigger para mantener search_vector actualizado
-- ========================================

CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar vector de búsqueda full-text
    NEW.search_vector :=
        setweight(to_tsvector('spanish', COALESCE(array_to_string(NEW.profession_tokens, ' '), '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(array_to_string(NEW.service_tokens, ' '), '')), 'B') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.city_normalized, '')), 'C') ||
        setweight(to_tsvector('spanish', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D');

    -- Actualizar timestamp
    NEW.updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_search_vector
    BEFORE INSERT OR UPDATE ON provider_search_index
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- ========================================
-- 4. Tabla de Métricas de Búsqueda
-- ========================================

CREATE TABLE IF NOT EXISTS search_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Datos de la búsqueda
    query_hash VARCHAR(64) NOT NULL,
    query_text TEXT NOT NULL,
    query_tokens TEXT[] NOT NULL,
    search_strategy VARCHAR(50) NOT NULL,

    -- Resultados
    total_results INTEGER NOT NULL DEFAULT 0,
    results_returned INTEGER NOT NULL DEFAULT 0,
    search_time_ms INTEGER NOT NULL,
    confidence_score FLOAT,

    -- Metadatos
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    filters_applied JSONB,
    used_ai_enhancement BOOLEAN DEFAULT false,
    cache_hit BOOLEAN DEFAULT false,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para métricas
CREATE INDEX idx_search_metrics_query_hash ON search_metrics(query_hash);
CREATE INDEX idx_search_metrics_created_at ON search_metrics(created_at DESC);
CREATE INDEX idx_search_metrics_search_strategy ON search_metrics(search_strategy);
CREATE INDEX idx_search_metrics_ai_enhancement ON search_metrics(used_ai_enhancement);

-- ========================================
-- 5. Tabla de Consultas Populares
-- ========================================

CREATE TABLE IF NOT EXISTS popular_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) NOT NULL UNIQUE,
    search_count INTEGER NOT NULL DEFAULT 1,
    last_searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    avg_results FLOAT DEFAULT 0.0,
    avg_confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para consultas populares
CREATE INDEX idx_popular_queries_count ON popular_queries(search_count DESC);
CREATE INDEX idx_popular_queries_hash ON popular_queries(query_hash);
CREATE INDEX idx_popular_queries_last_searched ON popular_queries(last_searched_at DESC);

-- ========================================
-- 6. Funciones de Utilidad para Búsqueda
-- ========================================

-- Función para búsqueda por tokens (performance optimizada)
CREATE OR REPLACE FUNCTION search_providers_by_tokens(
    p_tokens TEXT[],
    p_city_normalized VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    provider_id UUID,
    provider_data JSONB,
    confidence_score FLOAT,
    match_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        psi.provider_id,
        psi.provider_data,
        psi.confidence_score,
        -- Calcular cantidad de matches
        array_length(
            array(
                SELECT elem
                FROM unnest(p_tokens) elem
                WHERE elem = ANY(psi.profession_tokens OR psi.service_tokens OR psi.keywords)
            ), 1
        ) as match_count
    FROM provider_search_index psi
    WHERE
        psi.is_active = true
        AND (
            -- Buscar tokens en profession_tokens
            psi.profession_tokens && p_tokens
            OR
            -- Buscar tokens en service_tokens
            psi.service_tokens && p_tokens
            OR
            -- Buscar tokens en keywords
            psi.keywords && p_tokens
        )
        AND (
            p_city_normalized IS NULL
            OR psi.city_normalized = p_city_normalized
        )
    ORDER BY
        match_count DESC,
        psi.confidence_score DESC,
        psi.updated_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Función para búsqueda full-text
CREATE OR REPLACE FUNCTION search_providers_fulltext(
    p_query TEXT,
    p_city_normalized VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    provider_id UUID,
    provider_data JSONB,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        psi.provider_id,
        psi.provider_data,
        ts_rank(psi.search_vector, plainto_tsquery('spanish', p_query)) as rank
    FROM provider_search_index psi
    WHERE
        psi.is_active = true
        AND psi.search_vector @@ plainto_tsquery('spanish', p_query)
        AND (
            p_city_normalized IS NULL
            OR psi.city_normalized = p_city_normalized
        )
    ORDER BY
        rank DESC,
        psi.confidence_score DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 7. Vista Materializada para Estadísticas
-- ========================================

CREATE MATERIALIZED VIEW IF NOT EXISTS provider_search_stats AS
SELECT
    COUNT(*) as total_providers,
    COUNT(CASE WHEN city_normalized IS NOT NULL THEN 1 END) as providers_with_city,
    COUNT(DISTINCT city_normalized) as unique_cities,
    COUNT(DISTINCT unnest(profession_tokens)) as unique_professions,
    AVG(confidence_score) as avg_confidence,
    MAX(updated_at) as last_update
FROM provider_search_index
WHERE is_active = true;

-- Índice para la vista materializada
CREATE INDEX idx_provider_search_stats_total ON provider_search_stats(total_providers);

-- Función para refrescar la vista materializada
CREATE OR REPLACE FUNCTION refresh_provider_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY provider_search_stats;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 8. Triggers para mantenimiento automático
-- ========================================

-- Trigger para actualizar estadísticas cuando hay cambios significativos
CREATE OR REPLACE FUNCTION trigger_stats_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar estadísticas cada 100 cambios
    IF (SELECT COUNT(*) FROM provider_search_index) % 100 = 0 THEN
        PERFORM refresh_provider_stats();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_update_stats
    AFTER INSERT OR UPDATE OR DELETE ON provider_search_index
    FOR EACH STATEMENT EXECUTE FUNCTION trigger_stats_update();

-- ========================================
-- 9. Políticas de Limpieza (mantenimiento)
-- ========================================

-- Función para limpiar métricas antiguas (mantener último mes)
CREATE OR REPLACE FUNCTION cleanup_old_metrics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_metrics
    WHERE created_at < NOW() - INTERVAL '30 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Log de limpieza
    RAISE NOTICE 'Cleanup: Deleted % old metric records', deleted_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 10. Permisos y Configuración Final
-- ========================================

-- Asegurar que las tablas tengan los permisos correctos
-- (Ajustar según el usuario de tu aplicación)

-- GRANT SELECT, INSERT, UPDATE, DELETE ON provider_search_index TO tinkubot_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON search_metrics TO tinkubot_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON popular_queries TO tinkubot_app;
-- GRANT SELECT ON provider_search_stats TO tinkubot_app;

-- GRANT USAGE ON SCHEMA public TO tinkubot_app;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO tinkubot_app;

-- Configuración de PostgreSQL para mejor performance
-- (Estos settings deben ir en postgresql.conf o ser configurados por admin)

-- shared_preload_libraries = 'pg_trgm'  -- Para búsquedas difusas
-- random_page_cost = 1.1               -- Para SSDs
-- effective_cache_size = '4GB'         -- Ajustar según memoria disponible
-- work_mem = '64MB'                    -- Para operaciones de ordenamiento
-- maintenance_work_mem = '256MB'       -- Para índices