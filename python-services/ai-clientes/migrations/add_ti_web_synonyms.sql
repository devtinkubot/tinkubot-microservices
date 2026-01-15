-- ============================================================================
-- SINÓNIMOS DE SERVICIOS TI / INGENIERÍA
-- Plan: Fix - Mejoras de Búsqueda (Enero 15, 2026)
--
-- Este script agrega sinónimos de servicios TI/ingeniería y desarrollo web
-- a la tabla service_synonyms de Supabase.
--
-- BREAKING CHANGES: Este script usa ON CONFLICT DO NOTHING para evitar
-- duplicados y breaking changes. Es seguro ejecutarlo múltiples veces.
-- ============================================================================

-- Sinónimos para DESARROLLADOR (ya existe, agregar los que faltan)
INSERT INTO service_synonyms (canonical_profession, synonym) VALUES
-- Ingeniería de software / TI
('desarrollador', 'ingeniero en sistemas'),
('desarrollador', 'ingeniero de sistemas'),
('desarrollador', 'ingeniero de computación'),
('desarrollador', 'ingeniero en computación'),
('desarrollador', 'ingeniero informático'),
('desarrollador', 'ingeniero informatica'),
('desarrollador', 'systems engineer'),
('desarrollador', 'software engineer'),
('desarrollador', 'ingeniero de desarrollo'),
('desarrollador', 'ingeniero de software developer'),

-- Desarrollo web específico
('desarrollador', 'desarrollador web'),
('desarrollador', 'desarrollador de software'),
('desarrollador', 'programador web'),
('desarrollador', 'web developer'),
('desarrollador', 'web dev'),
('desarrollador', 'full stack developer'),
('desarrollador', 'fullstack'),
('desarrollador', 'full-stack'),
('desarrollador', 'backend developer'),
('desarrollador', 'frontend developer'),
('desarrollador', 'backend'),
('desarrollador', 'frontend'),

-- Servicios web (páginas, sitios, etc)
('desarrollador', 'pagina web'),
('desarrollador', 'paginas web'),
('desarrollador', 'página web'),
('desarrollador', 'páginas web'),
('desarrollador', 'sitio web'),
('desarrollador', 'sitios web'),
('desarrollador', 'sitios'),
('desarrollador', 'web'),
('desarrollador', 'desarrollo de sitios web'),
('desarrollador', 'desarrollo de paginas web'),
('desarrollador', 'desarrollo de páginas web'),
('desarrollador', 'creacion de paginas web'),
('desarrollador', 'creación de páginas web'),
('desarrollador', 'crear pagina web'),
('desarrollador', 'crear página web'),
('desarrollador', 'construir pagina web'),
('desarrollador', 'construir página web'),
('desarrollador', 'montar pagina web'),
('desarrollador', 'montar página web'),

-- E-commerce y aplicaciones
('desarrollador', 'aplicación web'),
('desarrollador', 'aplicacion web'),
('desarrollador', 'aplicaciones web'),
('desarrollador', 'app web'),
('desarrollador', 'apps web'),
('desarrollador', 'ecommerce'),
('desarrollador', 'e-commerce'),
('desarrollador', 'tienda online'),
('desarrollador', 'tienda en linea'),
('desarrollador', 'tienda electrónica'),
('desarrollador', 'blog'),
('desarrollador', 'blogs'),

-- Software general
('desarrollador', 'software'),
('desarrollador', 'desarrollo de software'),
('desarrollador', 'programación'),
('desarrollador', 'programacion'),
('desarrollador', 'sistema'),
('desarrollador', 'sistemas'),
('desarrollador', 'aplicación'),
('desarrollador', 'aplicacion'),
('desarrollador', 'aplicaciones'),
('desarrollador', 'base de datos'),
('desarrollador', 'bases de datos'),
('desarrollador', 'api'),
('desarrollador', 'apis'),
('desarrollador', 'integración'),
('desarrollador', 'integracion'),
('desarrollador', 'integraciones'),

-- Consultoría TI
('desarrollador', 'consultoría informática'),
('desarrollador', 'consultoria informatica'),
('desarrollador', 'consultor de sistemas'),
('desarrollador', 'consultor ti'),
('desarrollador', 'consultor it')
ON CONFLICT DO NOTHING;

-- Nueva profesión: DISEÑADOR WEB (si no existe)
INSERT INTO service_synonyms (canonical_profession, synonym) VALUES
('diseñador web', 'diseñador web'),
('diseñador web', 'disenador web'),
('diseñador web', 'diseño web'),
('diseñador web', 'diseño de paginas web'),
('diseñador web', 'diseño de páginas web'),
('diseñador web', 'diseño de sitios web'),
('diseñador web', 'web designer'),
('diseñador web', 'web design'),
('diseñador web', 'diseño ui'),
('diseñador web', 'diseño ux'),
('diseñador web', 'diseño ui/ux'),
('diseñador web', 'diseñador ui'),
('diseñador web', 'diseñador ux'),
('diseñador web', 'diseñador ui/ux'),
('diseñador web', 'diseñadora web'),
('diseñador web', 'diseñadora ui'),
('diseñador web', 'diseñadora ux'),
('diseñador web', 'maquetacion web'),
('diseñador web', 'maquetación web'),
('diseñador web', 'maquetador web'),
('diseñador web', 'diseño de interfaces'),
('diseñador web', 'diseño de experiencia de usuario'),
('diseñador web', 'diseño grafico web'),
('diseñador web', 'diseño gráfico web')
ON CONFLICT DO NOTHING;

-- Verificación: Mostrar cantidad de sinónimos agregados
SELECT
    canonical_profession,
    COUNT(*) as synonym_count,
    STRING_AGG(synonym, ', ' ORDER BY synonym) as synonyms_sample
FROM service_synonyms
WHERE canonical_profession IN ('desarrollador', 'diseñador web')
GROUP BY canonical_profession
ORDER BY canonical_profession;
