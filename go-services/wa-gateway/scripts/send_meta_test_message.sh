#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-tinkubot-wa-gateway}"
ACCOUNT_ID="${ACCOUNT_ID:-bot-clientes}"
DEFAULT_TO="${DEFAULT_TO:-593959091325}"
DEFAULT_TEXT="${DEFAULT_TEXT:-Prueba salida wa-gateway (Cloud API)}"

TO_RAW="${1:-$DEFAULT_TO}"
TEXT="${2:-$DEFAULT_TEXT}"

# Preserve raw JIDs for controlled @lid experiments; otherwise normalize to digits.
if [[ "$TO_RAW" == *"@"* ]]; then
  TO="$(printf '%s' "$TO_RAW" | tr -d ' ')"
else
  TO="$(printf '%s' "$TO_RAW" | tr -d ' +()-')"
fi

if [[ -z "$TO" ]]; then
  echo "error: destination number is empty" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker command not found" >&2
  exit 1
fi

PAYLOAD="$(python3 - <<'PY' "$TO" "$TEXT"
import json
import sys

to = sys.argv[1]
text = sys.argv[2]
print(json.dumps({
    "messaging_product": "whatsapp",
    "to": to,
    "type": "text",
    "text": {"body": text},
}, ensure_ascii=False))
PY
)"

echo "Sending test message from container: ${CONTAINER_NAME}"
echo "Account: ${ACCOUNT_ID}"
echo "To: ${TO}"

docker exec \
  -e ACCOUNT_ID="$ACCOUNT_ID" \
  -e PAYLOAD="$PAYLOAD" \
  "$CONTAINER_NAME" \
  /bin/sh -lc '
    set -eu
    case "${ACCOUNT_ID}" in
      bot-clientes)
        PHONE_NUMBER_ID="${META_PHONE_NUMBER_ID_CLIENTES:-}"
        ACCESS_TOKEN="${META_CLIENTES_ACCESS_TOKEN:-}"
        ;;
      bot-proveedores)
        PHONE_NUMBER_ID="${META_PHONE_NUMBER_ID_PROVEEDORES:-}"
        ACCESS_TOKEN="${META_PROVEEDORES_ACCESS_TOKEN:-}"
        ;;
      *)
        echo "error: unsupported ACCOUNT_ID=${ACCOUNT_ID}" >&2
        exit 1
        ;;
    esac
    : "${PHONE_NUMBER_ID:?phone number id missing in container env}"
    : "${ACCESS_TOKEN:?access token missing in container env}"
    API_VERSION="${META_GRAPH_API_VERSION:-v25.0}"

    wget -qO- \
      --header="Authorization: Bearer ${ACCESS_TOKEN}" \
      --header="Content-Type: application/json" \
      --post-data="${PAYLOAD}" \
      "https://graph.facebook.com/${API_VERSION}/${PHONE_NUMBER_ID}/messages"
    echo
  '

echo "Done. If response contains messages[].id (wamid...), outbound is OK."
