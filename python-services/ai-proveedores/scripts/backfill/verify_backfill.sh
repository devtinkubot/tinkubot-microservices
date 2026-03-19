#!/bin/bash
# Script de verificación post-backfill
# Uso: ./verify_backfill.sh

set -e

echo "🔍 Verificando estado post-backfill..."
echo ""

echo "1. Reviews pendientes sin provider_id:"
psql -c "SELECT COUNT(*) as orphan_reviews FROM provider_service_catalog_reviews WHERE provider_id IS NULL AND review_status = 'pending';"

echo ""
echo "2. Proveedores con servicios insertados:"
psql -c "SELECT COUNT(DISTINCT provider_id) as providers_with_services FROM provider_services;"

echo ""
echo "3. Servicios sin domain_code (pendientes de clasificación):"
psql -c "SELECT COUNT(*) as services_without_domain FROM provider_services WHERE domain_code IS NULL;"

echo ""
echo "4. Reviews por estado:"
psql -c "SELECT review_status, COUNT(*) as count FROM provider_service_catalog_reviews GROUP BY review_status ORDER BY count DESC;"

echo ""
echo "5. Últimas reviews creadas:"
psql -c "SELECT id, service_name, review_status, provider_id, created_at FROM provider_service_catalog_reviews ORDER BY created_at DESC LIMIT 10;"

echo ""
echo "✅ Verificación completada."
