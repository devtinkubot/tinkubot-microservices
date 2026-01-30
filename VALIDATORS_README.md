# Validadores de Calidad - TinkuBot Microservicios

Este directorio contiene scripts de validación de código para asegurar calidad antes de hacer push a GitHub.

## 🚀 Uso Rápido

```bash
# Validar todos los servicios
./validate_all.sh

# Validar solo servicios Python
./validate_quality.py

# Validar solo Go (wa-gateway)
./validate_go.sh

# Validar solo Node.js (frontend)
./validate_nodejs.sh
```

## 📋 Validadores por Servicio

### 1. Python (`validate_quality.py`)
**Servicios:** ai-clientes, ai-proveedores, av-proveedores, search-token

**Validaciones:**
- ✅ Formato de código (Black)
- ✅ Importaciones ordenadas (isort)
- ✅ Linting (Flake8)
- ✅ Type checking (MyPy)
- ✅ Seguridad (Bandit)
- ✅ Sintaxis Python

**Uso:**
```bash
python validate_quality.py                    # Validar todos
python validate_quality.py --service ai-clientes  # Validar uno
python validate_quality.py --fix                 # Corregir automáticamente
```

### 2. Go (`validate_go.sh`)
**Servicio:** go-services/wa-gateway

**Validaciones:**
- ✅ Formato de código (gofmt, goimports)
- ✅ Análisis estático (go vet)
- ✅ Linting (golangci-lint, opcional)
- ✅ Seguridad (gosec)
- ✅ Pruebas unitarias (go test)

**Uso:**
```bash
./validate_go.sh
```

**Requisitos:**
- Go 1.21+

### 3. Node.js (`validate_nodejs.sh`)
**Servicio:** nodejs-services/frontend

**Validaciones:**
- ✅ Formato de código (Prettier)
- ✅ Linting (ESLint)
- ✅ Type checking (TypeScript)
- ✅ Pruebas unitarias (npm test)

**Uso:**
```bash
./validate_nodejs.sh
```

**Requisitos:**
- Node.js 20+
- Dependencias instaladas (node_modules/)

## 🔄 Integración con CI/CD

### GitHub Actions (recomendado)

```yaml
name: Quality Check

on: [push, pull_request]

jobs:
  quality-check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python tools
        run: |
          pip install black isort flake8 mypy bandit

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install Go
        uses: actions/setup-go@v4
        with:
          go-version: '1.21'

      - name: Run Python validator
        run: python validate_quality.py

      - name: Run Go validator
        run: ./validate_go.sh

      - name: Run Node.js validator
        run: ./validate_nodejs.sh
```

### Pre-commit Hook (opcional)

```bash
# Instalar pre-commit
pip install pre-commit

# Crear .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: validate-all
        name: Validate all services
        entry: ./validate_all.sh
        language: system
EOF

pre-commit install
```

## 🛠️ Troubleshooting

### Error: "permiso denegado"
```bash
chmod +x validate_*.sh
```

### Error: "go: command not found"
```bash
# Instalar Go
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

### Error: "node_modules not found"
```bash
cd nodejs-services/frontend
npm ci
cd ../..
```

## 📊 Salida Esperada

### Ejecución Exitosa:
```
╔══════════════════════════════════════════════════════════════╗
║            🔍 VALIDADOR DE CALIDAD - TINKUBOT MICROSERVICIOS     ║
║                   Antes de subir a GitHub                        ║
╚══════════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════════
  Python Services (ai-clientes, ai-proveedores)
════════════════════════════════════════════════════════════════
[... validaciones ...]

✅ PYTHON SERVICES - PASÓ

════════════════════════════════════════════════════════════════
  Go Service (wa-gateway)
════════════════════════════════════════════════════════════════
[... validaciones ...]

✅ GO SERVICE - PASÓ

════════════════════════════════════════════════════════════════
  Node.js Service (frontend)
════════════════════════════════════════════════════════════════
[... validaciones ...]

✅ NODE.JS SERVICE - PASÓ

╔══════════════════════════════════════════════════════════════╗
║                         RESUMEN FINAL                             ║
╚══════════════════════════════════════════════════════════════╝
PYTHON SERVICES: ✅ PASSED
GO SERVICE: ✅ PASSED
NODE.JS SERVICE: ✅ PASSED

Resultados: 3/3 validaciones pasaron

🎉 Todas las validaciones pasaron. Código listo para GitHub!
```

## 🔧 Herramientas Utilizadas

| Python | Go | Node.js |
|--------|-----|----------|
| black | gofmt | prettier |
| isort | goimports | eslint |
| flake8 | go vet | tsc |
| mypy | golangci-lint | npm test |
| bandit | gosec | - |

## 📝 Notas

- Los validadores deben ejecutarse desde la raíz del proyecto
- Instalan automáticamente las herramientas necesarias (si es posible)
- Usan códigos de colores para mejor legibilidad
- Retornan exit code 0 si todo está bien, 1 si hay errores
- Pueden usarse individualmente o todos juntos con `validate_all.sh`
