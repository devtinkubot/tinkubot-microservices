#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: ./run_backfill.sh [--apply] [--link-only] [--seed-services-only]

Defaults to dry-run mode. Use --apply to write changes.
EOF
}

ARGS=()

for arg in "$@"; do
  case "$arg" in
    --apply)
      ARGS+=("--apply")
      ;;
    --link-only)
      ARGS+=("--link-only")
      ;;
    --seed-services-only)
      ARGS+=("--seed-services-only")
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

python3 "$SCRIPT_DIR/normalizar_proveedores_limbo.py" "${ARGS[@]}"
