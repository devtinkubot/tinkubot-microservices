-- Crear tabla service_synonyms para catálogo dinámico de servicios
-- Esta tabla permite actualizar sinónimos sin reiniciar el servicio

CREATE TABLE IF NOT EXISTS service_synonyms (
    id BIGSERIAL PRIMARY KEY,
    canonical_profession VARCHAR(100) NOT NULL,
    synonym VARCHAR(200) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_service_synonyms_canonical ON service_synonyms(canonical_profession);
CREATE INDEX IF NOT EXISTS idx_service_synonyms_synonym ON service_synonyms(synonym);
CREATE INDEX IF NOT EXISTS idx_service_synonyms_active ON service_synonyms(active);

-- Insertar datos iniciales desde el catálogo estático actual
INSERT INTO service_synonyms (canonical_profession, synonym) VALUES
-- Plomero
('plomero', 'plomero'),
('plomero', 'plomeria'),
('plomero', 'plomería'),
('plomero', 'gasfitero'),
('plomero', 'gasfiteria'),
('plomero', 'fontanero'),
-- Electricista
('electricista', 'electricista'),
('electricista', 'electricistas'),
-- Médico
('médico', 'médico'),
('médico', 'medico'),
('médico', 'doctor'),
('médico', 'doctora'),
-- Mecánico
('mecánico', 'mecanico'),
('mecánico', 'mecánico'),
('mecánico', 'mecanicos'),
('mecánico', 'mecanica automotriz'),
('mecánico', 'taller mecanico'),
-- Pintor
('pintor', 'pintor'),
('pintor', 'pintura'),
('pintor', 'pintores'),
-- Albañil
('albañil', 'albañil'),
('albañil', 'albanil'),
('albañil', 'maestro de obra'),
-- Cerrajero
('cerrajero', 'cerrajero'),
('cerrajero', 'cerrajeria'),
-- Veterinario
('veterinario', 'veterinario'),
('veterinario', 'veterinaria'),
-- Chef
('chef', 'chef'),
('chef', 'cocinero'),
('chef', 'cocinera'),
-- Mesero
('mesero', 'mesero'),
('mesero', 'mesera'),
('mesero', 'camarero'),
('mesero', 'camarera'),
-- Profesor
('profesor', 'profesor'),
('profesor', 'profesora'),
('profesor', 'maestro'),
('profesor', 'maestra'),
-- Bartender
('bartender', 'bartender'),
('bartender', 'barman'),
-- Carpintero
('carpintero', 'carpintero'),
('carpintero', 'carpinteria'),
-- Jardinero
('jardinero', 'jardinero'),
('jardinero', 'jardineria'),
-- Marketing (INCLUYENDO GESTOR DE REDES SOCIALES)
('marketing', 'marketing'),
('marketing', 'marketing digital'),
('marketing', 'mercadotecnia'),
('marketing', 'publicidad'),
('marketing', 'publicista'),
('marketing', 'agente de publicidad'),
('marketing', 'campanas de marketing'),
('marketing', 'campanas publicitarias'),
('marketing', 'community manager'),
('marketing', 'gestor de redes sociales'),
('marketing', 'gestor de contenido'),
('marketing', 'social media'),
('marketing', 'social media manager'),
('marketing', 'redes sociales'),
('marketing', 'administrador de redes sociales'),
('marketing', 'gestion de redes sociales'),
('marketing', 'community management'),
('marketing', 'digital marketing'),
('marketing', 'social media marketing'),
-- Diseñador gráfico
('diseñador gráfico', 'diseño grafico'),
('diseñador gráfico', 'diseno grafico'),
('diseñador gráfico', 'diseñador grafico'),
('diseñador gráfico', 'designer grafico'),
('diseñador gráfico', 'graphic designer'),
('diseñador gráfico', 'diseñador'),
-- Consultor
('consultor', 'consultor'),
('consultor', 'consultoria'),
('consultor', 'consultoría'),
('consultor', 'asesor'),
('consultor', 'asesoria'),
('consultor', 'asesoría'),
('consultor', 'consultor de negocios'),
-- Desarrollador
('desarrollador', 'desarrollador'),
('desarrollador', 'programador'),
('desarrollador', 'developer'),
('desarrollador', 'desarrollo web'),
('desarrollador', 'software developer'),
('desarrollador', 'ingeniero de software'),
-- Contador
('contador', 'contador'),
('contador', 'contadora'),
('contador', 'contable'),
('contador', 'contabilidad'),
('contador', 'finanzas'),
-- Abogado
('abogado', 'abogado'),
('abogado', 'abogada'),
('abogado', 'legal'),
('abogado', 'asesoria legal'),
('abogado', 'asesoría legal'),
('abogado', 'servicios legales')
ON CONFLICT DO NOTHING;

-- Crear función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger para actualizar updated_at
DROP TRIGGER IF EXISTS update_service_synonyms_updated_at ON service_synonyms;
CREATE TRIGGER update_service_synonyms_updated_at
    BEFORE UPDATE ON service_synonyms
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comentario de la tabla
COMMENT ON TABLE service_synonyms IS 'Catálogo dinámico de sinónimos de servicios. Permite actualizar sin reiniciar el servicio.';
COMMENT ON COLUMN service_synonyms.canonical_profession IS 'Profesión canónica (ej: "marketing")';
COMMENT ON COLUMN service_synonyms.synonym IS 'Sinónimo que mapea a la profesión canónica (ej: "community manager", "gestor de redes sociales")';
