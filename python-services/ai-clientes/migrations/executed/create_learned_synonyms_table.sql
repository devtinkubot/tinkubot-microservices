-- ============================================================================
-- TABLA: learned_synonyms (Sistema de Aprendizaje Automático)
-- Plan: Mejoras Inmediatas al Sistema de Búsqueda (Enero 2026)
-- ============================================================================

-- Esta tabla almacena sinónimos aprendidos automáticamente de búsquedas exitosas
-- Los sinónimos aprendidos requieren aprobación manual antes de pasar a service_synonyms

CREATE TABLE IF NOT EXISTS learned_synonyms (
    id BIGSERIAL PRIMARY KEY,
    canonical_profession VARCHAR(100) NOT NULL,
    learned_synonym VARCHAR(200) NOT NULL,
    source_query TEXT NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.50,  -- 0.00 a 1.00
    match_count INTEGER DEFAULT 1,  -- Cuántas veces se ha detectado
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    approved_by VARCHAR(100),  -- Usuario que aprobó
    approved_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraint: No duplicados
    UNIQUE(canonical_profession, learned_synonym)
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_learned_synonyms_status ON learned_synonyms(status);
CREATE INDEX IF NOT EXISTS idx_learned_synonyms_canonical ON learned_synonyms(canonical_profession);
CREATE INDEX IF NOT EXISTS idx_learned_synonyms_confidence ON learned_synonyms(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_learned_synonyms_match_count ON learned_synonyms(match_count DESC);

-- Índice compuesto para pendientes ordenados por prioridad
CREATE INDEX IF NOT EXISTS idx_learned_synonyms_pending_priority
ON learned_synonyms(status, confidence_score DESC, match_count DESC)
WHERE status = 'pending';

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_learned_synonyms_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para updated_at
DROP TRIGGER IF EXISTS update_learned_synonyms_updated_at_trigger ON learned_synonyms;
CREATE TRIGGER update_learned_synonyms_updated_at_trigger
    BEFORE UPDATE ON learned_synonyms
    FOR EACH ROW
    EXECUTE FUNCTION update_learned_synonyms_updated_at();

-- Comentarios
COMMENT ON TABLE learned_synonyms IS 'Sinónimos aprendidos automáticamente de búsquedas exitosas. Requieren aprobación manual.';
COMMENT ON COLUMN learned_synonyms.canonical_profession IS 'Profesión canónica (ej: "marketing")';
COMMENT ON COLUMN learned_synonyms.learned_synonym IS 'Sinónimo aprendido (ej: "social media expert")';
COMMENT ON COLUMN learned_synonyms.source_query IS 'Query original del usuario que generó el aprendizaje';
COMMENT ON COLUMN learned_synonyms.confidence_score IS 'Confianza del aprendizaje (0.00-1.00). Basado en: match_count, relevance, etc.';
COMMENT ON COLUMN learned_synonyms.match_count IS 'Cuántas veces se ha detectado este sinónimo en búsquedas exitosas';
COMMENT ON COLUMN learned_synonyms.status IS 'Estado: pending=esperando aprobación, approved=aprobado, rejected=rechazado';
COMMENT ON COLUMN learned_synonyms.approved_by IS 'Usuario/admin que aprobó el sinónimo';

-- Verificación: Mostrar estructura de la tabla
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'learned_synonyms'
ORDER BY ordinal_position;
