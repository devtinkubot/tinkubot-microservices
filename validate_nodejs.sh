#!/bin/bash
# Validador de calidad para Node.js - TinkuBot Frontend
# Ejecuta validaciones de calidad antes de subir a GitHub

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SERVICE_DIR="nodejs-services/frontend"

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     🔍 VALIDADOR DE CALIDAD - TINKUBOT NODE.JS (FRONTEND)    ║"
    echo "║                 Antes de subir a GitHub                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${WHITE}Este script ejecuta las siguientes validaciones:"
    echo "• Formato de código (Prettier)"
    echo "• Linting (ESLint)"
    echo "• Chequeo de TypeScript (tsc --noEmit)"
    echo "• Pruebas unitarias (npm test)"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_tool() {
    if command -v "$1" &> /dev/null; then
        print_success "$1 está instalado"
        return 0
    else
        print_warning "$1 no está instalado"
        return 1
    fi
}

# Cambiar al directorio del servicio
cd "$(dirname "$0")"
if [ ! -d "$SERVICE_DIR" ]; then
    print_error "Directorio $SERVICE_DIR no encontrado"
    exit 1
fi

cd "$SERVICE_DIR"
print_info "Validando servicio en: $(pwd)"

# Verificar si node_modules existe
if [ ! -d "node_modules" ]; then
    print_info "Instalando dependencias..."
    npm ci
fi

print_banner

# 1. Validar formato con Prettier
echo -e "\n${BOLD}${BLUE}📝 VALIDACIÓN DE FORMATO (PRETTIER)${NC}"
if ! command -v npx &> /dev/null; then
    print_error "npx no encontrado"
    exit 1
fi

if npx prettier --check . '*.js' '*.ts' '*.json' &> /dev/null; then
    print_success "Código formateado correctamente (Prettier)"
else
    print_error "Código mal formateado. Ejecuta: npx prettier --write ."
    npx prettier --check . '*.js' '*.ts' '*.json' | head -20
    exit 1
fi

# 2. ESLint
echo -e "\n${BOLD}${BLUE}🔍 LINTING (ESLINT)${NC}"
if npx eslint . --ext .js,.ts,.tsx --max-warnings 0; then
    print_success "Linting (ESLint) - OK"
else
    print_error "Linting (ESLint) - ERROR"
    exit 1
fi

# 3. TypeScript - Type checking
echo -e "\n${BOLD}${BLUE}🔧 VALIDACIÓN DE TIPOS (TSC)${NC}"
# Buscar archivos tsconfig.json
if [ -f "tsconfig.json" ] || [ -f "apps/admin-dashboard/tsconfig.json" ]; then
    print_info "Compilando TypeScript..."
    if npm run build 2>&1 | grep -q "error"; then
        print_error "TypeScript compilation - FAILED"
        exit 1
    else
        print_success "TypeScript compilation - OK"
    fi
else
    print_info "No tsconfig.json encontrado, saltando validación de tipos"
fi

# 4. npm test - Pruebas unitarias (si existen)
echo -e "\n${BOLD}${BLUE}🧪 PRUEBAS UNITARIAS (NPM TEST)${NC}"
if grep -q '"test"' package.json; then
    print_info "Ejecutando pruebas..."
    if npm test 2>&1 | grep -q "failing"; then
        print_error "Pruebas unitarias - FALLARON"
        exit 1
    else
        print_success "Pruebas unitarias - OK"
    fi
else
    print_info "No hay tests configurados, saltando..."
fi

# Resumen
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                    ✅ VALIDACIÓN COMPLETADA                    ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"

print_success "🎉 Código Node.js listo para GitHub!"
