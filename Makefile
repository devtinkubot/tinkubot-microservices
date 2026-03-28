.PHONY: help validate validate-all validate-python validate-go validate-node validate-elixir format-elixir

ELIXIR_IMAGE ?= elixir:1.17-slim
ELIXIR_SERVICE_DIR := elixir-services/provider-onboarding-worker

help:
	@echo "Targets disponibles:"
	@echo "  make validate        - Ejecuta la validación completa del repo"
	@echo "  make validate-all    - Alias de validate"
	@echo "  make validate-python - Ejecuta la validación de Python"
	@echo "  make validate-go     - Ejecuta la validación de Go"
	@echo "  make validate-node   - Ejecuta la validación de Node.js"
	@echo "  make validate-elixir - Ejecuta la validación de Elixir"
	@echo "  make format-elixir   - Formatea el worker Elixir"

validate: validate-all

validate-all:
	./validate_all.sh

validate-python:
	./validate_all.sh --python

validate-go:
	./validate_all.sh --go

validate-node:
	./validate_all.sh --node

validate-elixir:
	./validate_elixir.sh

format-elixir:
	@set -e; \
	if command -v mix >/dev/null 2>&1; then \
		cd "$(ELIXIR_SERVICE_DIR)" && mix format; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm \
			-v "$(CURDIR)/$(ELIXIR_SERVICE_DIR):/app" \
			-w /app \
			-e MIX_ENV=dev \
			-e HEX_HOME=/tmp/hex \
			-e MIX_HOME=/tmp/mix \
			-e XDG_CACHE_HOME=/tmp/cache \
			"$(ELIXIR_IMAGE)" \
			bash -lc 'set -e; apt-get update >/dev/null; apt-get install -y --no-install-recommends ca-certificates git >/dev/null; rm -rf /var/lib/apt/lists/*; mix local.hex --force >/dev/null; mix local.rebar --force >/dev/null; mix deps.get >/dev/null; mix format'; \
	else \
		echo "Neither mix nor docker is available for Elixir formatting"; \
		exit 1; \
	fi
