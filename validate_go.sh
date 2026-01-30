#!/bin/bash
# Validador de calidad para Go - TinkuBot wa-gateway
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

SERVICE_DIR="go-services/wa-gateway"

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║       🔍 VALIDADOR DE CALIDAD - TINKUBOT GO (wa-gateway)      ║"
    echo "║                 Antes de subir a GitHub                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${WHITE}Este script ejecuta las siguientes validaciones:"
    echo "• Formato de código (gofmt, goimports)"
    echo "• Análisis estático (go vet)"
    echo "• Linting (golangci-lint si está disponible)"
    echo "• Seguridad (gosec)"
    echo "• Pruebas unitarias (go test)"
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

print_banner

# 1. Validar formato con gofmt
echo -e "\n${BOLD}${BLUE}📝 VALIDACIÓN DE FORMATO (GOFMT)${NC}"
if gofmt -l . | grep -q "\.go$"; then
    print_error "Código mal formateado. Ejecuta: gofmt -w ."
    gofmt -d .
    exit 1
else
    print_success "Código correctamente formateado (gofmt)"
fi

# 2. Validar con goimports
echo -e "\n${BOLD}${BLUE}📦 VALIDACIÓN DE IMPORTACIONES (GOIMPORTS)${NC}"
if ! command -v goimports &> /dev/null; then
    print_info "goimports no está instalado, instalando..."
    go install golang.org/x/tools/cmd/goimports@latest
fi
if goimports -l . | grep -q "\.go$"; then
    print_error "Importaciones desordenadas. Ejecuta: goimports -w ."
    goimports -d .
    exit 1
else
    print_success "Importaciones correctamente ordenadas (goimports)"
fi

# 3. go vet - Análisis estático
echo -e "\n${BOLD}${BLUE}🔍 ANÁLISIS ESTÁTICO (GO VET)${NC}"
if go vet ./...; then
    print_success "Análisis estático (go vet) - OK"
else
    print_error "Análisis estático (go vet) - ERROR"
    exit 1
fi

# 4. golangci-lint si está disponible
echo -e "\n${BOLD}${BLUE}🔎 LINTING (GOLANGCI-LINT)${NC}"
if command -v golangci-lint &> /dev/null; then
    if golangci-lint run --timeout 5m; then
        print_success "Linting (golangci-lint) - OK"
    else
        print_error "Linting (golangci-lint) - ERROR"
        exit 1
    fi
else
    print_info "golangci-lint no está instalado (opcional)"
fi

# 5. gosec - Seguridad
echo -e "\n${BOLD}${BLUE}🔒 VALIDACIÓN DE SEGURIDAD (GOSEC)${NC}"
if ! command -v gosec &> /dev/null; then
    print_info "gosec no está instalado, instalando..."
    go install github.com/securecodewar/gosec/v2/cmd/gosec@latest
fi
if gosec -no-fail -stdout -format=json ./... 2>&1 | grep -q '"Issues":\[\]'; then
    print_success "Seguridad (gosec) - No issues found"
else
    print_warning "Seguridad (gosec) - Issues encontrados (revisar)"
fi

# 6. go test - Pruebas unitarias
echo -e "\n${BOLD}${BLUE}🧪 PRUEBAS UNITARIAS (GO TEST)${NC}"
if go test -v ./... 2>&1 | grep -q "FAIL"; then
    print_error "Pruebas unitarias - FALLARON"
    exit 1
else
    print_success "Pruebas unitarias - OK"
fi

# Resumen
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                    ✅ VALIDACIÓN COMPLETADA                    ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"

print_success "🎉 Código Go listo para GitHub!"
