#!/bin/bash
# Script para ejecutar tests de ai-proveedores

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Tests de ai-proveedores${NC}"
echo -e "${YELLOW}  Sprint-1.12 - Contract Tests${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Cambiar al directorio del script
cd "$(dirname "$0")"

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: main.py no encontrado. Ejecutar desde el directorio ai-proveedores${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Directorio correcto: $(pwd)${NC}"
echo ""

# Opción 1: Ejecutar todos los tests
if [ "$1" == "--all" ] || [ -z "$1" ]; then
    echo -e "${YELLOW}Ejecutando todos los tests...${NC}"
    pytest tests/ -v
    echo -e "${GREEN}✓ Tests completados${NC}"
fi

# Opción 2: Solo tests de endpoints
if [ "$1" == "--endpoints" ]; then
    echo -e "${YELLOW}Ejecutando solo tests de endpoints...${NC}"
    pytest tests/api/test_endpoints.py -v
    echo -e "${GREEN}✓ Tests de endpoints completados${NC}"
fi

# Opción 3: Con coverage
if [ "$1" == "--coverage" ]; then
    echo -e "${YELLOW}Ejecutando tests con coverage...${NC}"
    pytest tests/ --cov=. --cov-report=html --cov-report=term
    echo -e "${GREEN}✓ Coverage report generado en htmlcov/${NC}"
fi

# Opción 4: Test específico
if [ "$1" == "--test" ]; then
    if [ -z "$2" ]; then
        echo -e "${RED}Error: Especificar nombre del test${NC}"
        echo "Uso: ./run_tests.sh --test <test_name>"
        exit 1
    fi
    echo -e "${YELLOW}Ejecutando test específico: $2${NC}"
    pytest tests/api/test_endpoints.py -k "$2" -v
fi

# Opción 5: Ver estructura de tests
if [ "$1" == "--list" ]; then
    echo -e "${YELLOW}Estructura de tests:${NC}"
    pytest tests/ --collect-only
fi

# Opción 6: Instalar dependencias
if [ "$1" == "--install" ]; then
    echo -e "${YELLOW}Instalando dependencias de testing...${NC}"
    pip install -r requirements.txt
    pip install -r tests/requirements-test.txt
    echo -e "${GREEN}✓ Dependencias instaladas${NC}"
fi

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Uso:${NC}"
echo -e "  ./run_tests.sh [--all|--endpoints|--coverage|--test <name>--list|--install]"
echo -e "${YELLOW}========================================${NC}"
