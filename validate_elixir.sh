#!/bin/bash
# Validador de calidad para Elixir - TinkuBot provider onboarding worker

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
WHITE='\033[1;37m'
NC='\033[0m'

SERVICE_DIR="elixir-services/provider-onboarding-worker"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELIXIR_IMAGE="${ELIXIR_IMAGE:-elixir:1.17-slim}"
USE_DOCKER_ELIXIR="${USE_DOCKER_ELIXIR:-auto}"

has_mix() {
    command -v mix >/dev/null 2>&1
}

has_docker() {
    command -v docker >/dev/null 2>&1
}

run_in_docker() {
    local service_abs
    service_abs="$ROOT_DIR/$SERVICE_DIR"

    print_info "Usando Docker para ejecutar mix en ${ELIXIR_IMAGE}"

    docker run --rm \
        -v "${service_abs}:/app" \
        -w /app \
        -e MIX_ENV=dev \
        -e HEX_HOME=/tmp/hex \
        -e MIX_HOME=/tmp/mix \
        -e XDG_CACHE_HOME=/tmp/cache \
        "${ELIXIR_IMAGE}" \
        bash -lc '
            set -e
            apt-get update
            apt-get install -y --no-install-recommends ca-certificates git
            rm -rf /var/lib/apt/lists/*
            mix local.hex --force
            mix local.rebar --force
            mix deps.get
            mix format --check-formatted
            MIX_ENV=prod mix compile --warnings-as-errors
            if [ -d test ] && find test -type f \( -name "*_test.exs" -o -name "*_tests.exs" \) | grep -q .; then
                mix test
            else
                echo "No hay archivos de prueba; saltando mix test"
            fi
        '
}

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║         🔍 VALIDADOR DE CALIDAD - TINKUBOT ELIXIR           ║"
    echo "║              provider-onboarding-worker                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${WHITE}Este script ejecuta las siguientes validaciones:"
    echo "• Formato de código (mix format)"
    echo "• Compilación (mix compile --warnings-as-errors)"
    echo "• Pruebas unitarias (mix test, si existen)"
    echo -e "${NC}"
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

has_test_files() {
    [ -d test ] || return 1
    find test -type f \( -name '*_test.exs' -o -name '*_tests.exs' \) | grep -q .
}

cd "$ROOT_DIR"

if [ ! -d "$SERVICE_DIR" ]; then
    print_error "Directorio $SERVICE_DIR no encontrado"
    exit 1
fi

cd "$SERVICE_DIR"
print_info "Validando servicio en: $(pwd)"

print_banner

if [ ! -f "mix.exs" ]; then
    print_error "mix.exs no encontrado en $SERVICE_DIR"
    exit 1
fi

if [ ! -f "mix.lock" ]; then
    print_warning "mix.lock no encontrado; se resolverán deps al vuelo"
fi

if [ "$USE_DOCKER_ELIXIR" = "auto" ]; then
    if has_mix; then
        USE_DOCKER_ELIXIR="0"
    elif has_docker; then
        USE_DOCKER_ELIXIR="1"
    else
        USE_DOCKER_ELIXIR="0"
    fi
fi

if [ "$USE_DOCKER_ELIXIR" = "1" ]; then
    if ! has_docker; then
        print_error "Docker no está disponible para ejecutar Elixir"
        exit 1
    fi

    if ! run_in_docker; then
        print_error "Validación Elixir en Docker - ERROR"
        exit 1
    fi

    print_success "Validación Elixir en Docker - OK"
else
    if ! has_mix; then
        print_error "mix no está instalado y el modo Docker está deshabilitado"
        exit 1
    fi

    print_info "Resolviendo dependencias"
    mix deps.get

    echo -e "\n${BOLD}${BLUE}📝 VALIDACIÓN DE FORMATO (MIX FORMAT)${NC}"
    if mix format --check-formatted; then
        print_success "Formato Elixir correcto (mix format)"
    else
        print_error "Código Elixir mal formateado. Ejecuta: mix format"
        exit 1
    fi

    echo -e "\n${BOLD}${BLUE}🔧 VALIDACIÓN DE COMPILACIÓN (MIX COMPILE)${NC}"
    if mix compile --warnings-as-errors; then
        print_success "Compilación Elixir - OK"
    else
        print_error "Compilación Elixir - ERROR"
        exit 1
    fi

    echo -e "\n${BOLD}${BLUE}🧪 PRUEBAS UNITARIAS (MIX TEST)${NC}"
    if has_test_files; then
        if mix test; then
            print_success "Pruebas Elixir - OK"
        else
            print_error "Pruebas Elixir - FALLARON"
            exit 1
        fi
    else
        print_warning "No hay archivos de prueba; saltando mix test"
    fi
fi

echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                    ✅ VALIDACIÓN COMPLETADA                  ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"

print_success "🎉 Código Elixir listo para GitHub!"
