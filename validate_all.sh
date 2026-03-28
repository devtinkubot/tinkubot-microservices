#!/bin/bash
# Validador de calidad unificado - TinkuBot Microservicios
# Ejecuta validaciones de calidad para Python, Go, Node.js y Elixir

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

RUN_PYTHON=1
RUN_GO=1
RUN_NODE=1
RUN_ELIXIR=1

usage() {
    cat <<'EOF'
Uso: ./validate_all.sh [--python|--go|--node|--elixir|--all]

Validador unificado de calidad del repo.
Sin argumentos ejecuta Python, Go y Node.js.

Opciones:
  --python   Ejecuta solo la validación de Python
  --go       Ejecuta solo la validación de Go
  --node     Ejecuta solo la validación de Node.js
  --elixir   Ejecuta solo la validación de Elixir
  --all      Ejecuta todos los validadores
  -h, --help Muestra esta ayuda
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --python)
            RUN_PYTHON=1
            RUN_GO=0
            RUN_NODE=0
            ;;
        --go)
            RUN_PYTHON=0
            RUN_GO=1
            RUN_NODE=0
            ;;
        --node)
            RUN_PYTHON=0
            RUN_GO=0
            RUN_NODE=1
            RUN_ELIXIR=0
            ;;
        --elixir)
            RUN_PYTHON=0
            RUN_GO=0
            RUN_NODE=0
            RUN_ELIXIR=1
            ;;
        --all)
            RUN_PYTHON=1
            RUN_GO=1
            RUN_NODE=1
            RUN_ELIXIR=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Argumento desconocido: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            🔍 VALIDADOR DE CALIDAD - TINKUBOT MICROSERVICIOS     ║"
    echo "║                   Un solo entrypoint, varios stacks              ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

# Ejecutar validadores según modo
if [ "$RUN_PYTHON" -eq 1 ]; then
    run_validator "Python Services (ai-clientes, ai-proveedores, ai-search)" "./validate_quality.py"
fi

if [ "$RUN_GO" -eq 1 ]; then
    run_validator "Go Service (wa-gateway)" "./validate_go.sh"
fi

if [ "$RUN_NODE" -eq 1 ]; then
    run_validator "Node.js Service (frontend)" "./validate_nodejs.sh"
fi

if [ "$RUN_ELIXIR" -eq 1 ]; then
    run_validator "Elixir Service (provider-onboarding-worker)" "./validate_elixir.sh"
fi

# Resumen final
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                         RESUMEN FINAL                        ║${NC}"
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
