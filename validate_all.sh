#!/bin/bash
# Validador de Calidad Unificado - TinkuBot Microservicios
# Ejecuta validaciones de calidad para Python, Go y Node.js

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            🔍 VALIDADOR DE CALIDAD - TINKUBOT MICROSERVICIOS     ║"
    echo "║                   Antes de subir a GitHub                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_section() {
    echo -e "\n${BOLD}${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════${NC}"
}

# Cambiar al directorio raíz del proyecto
cd "$(dirname "$0")"

print_banner

# Resultados
declare -A results
total_passed=0
total_checks=0

run_validator() {
    local name="$1"
    local script="$2"

    print_section "$name"

    if [ -f "$script" ]; then
        if bash "$script"; then
            results[$name]="PASSED"
            ((total_passed++))
            ((total_checks++))
            print_success "$name - PASÓ"
        else
            results[$name]="FAILED"
            ((total_checks++))
            print_error "$name - FALLÓ"
        fi
    else
        print_warning "Script $script no encontrado, omitiendo..."
    fi
}

# Ejecutar validadores en orden
run_validator "Python Services (ai-clientes, ai-proveedores)" "./validate_quality.py"
run_validator "Go Service (wa-gateway)" "./validate_go.sh"
run_validator "Node.js Service (frontend)" "./validate_nodejs.sh"

# Resumen final
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                         RESUMEN FINAL                             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"

for check_name in "${!results[@]}"; do
    status="${results[$check_name]}"
    if [ "$status" = "PASSED" ]; then
        color="$GREEN"
        symbol="✅"
    else
        color="$RED"
        symbol="❌"
    fi
    echo -e "${color}${check_name}${NC}: ${symbol} ${status}"
done

echo -e "\n${WHITE}Resultados: ${GREEN}${total_passed}${NC}/${total_checks} validaciones pasaron${NC}"

if [ "$total_passed" -eq "$total_checks" ]; then
    print_success "🎉 Todas las validaciones pasaron. Código listo para GitHub!"
    exit 0
else
    print_error "⚠️  $((total_checks - total_passed)) validaciones fallaron."
    print_info "Corrige los problemas antes de subir a GitHub."
    exit 1
fi
