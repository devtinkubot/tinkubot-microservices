#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-tinkubot-wa-gateway}"
DEFAULT_TO="${DEFAULT_TO:-593959091325}"
DEFAULT_TEXT="${DEFAULT_TEXT:-Prueba salida wa-gateway (Cloud API)}"

TO_RAW="${1:-$DEFAULT_TO}"
TEXT="${2:-$DEFAULT_TEXT}"

# Normalize common phone formats to E.164 digits without plus/spaces.
TO="$(printf '%s' "$TO_RAW" | tr -d ' +()-')"

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
echo "To: ${TO}"

docker exec \
  -e PAYLOAD="$PAYLOAD" \
  "$CONTAINER_NAME" \
  /bin/sh -lc '
    set -eu
    : "${META_PHONE_NUMBER_ID_CLIENTES:?META_PHONE_NUMBER_ID_CLIENTES missing in container env}"
    : "${META_CLIENTES_ACCESS_TOKEN:?META_CLIENTES_ACCESS_TOKEN missing in container env}"
    API_VERSION="${META_GRAPH_API_VERSION:-v25.0}"

    wget -qO- \
      --header="Authorization: Bearer ${META_CLIENTES_ACCESS_TOKEN}" \
      --header="Content-Type: application/json" \
      --post-data="${PAYLOAD}" \
      "https://graph.facebook.com/${API_VERSION}/${META_PHONE_NUMBER_ID_CLIENTES}/messages"
    echo
  '

echo "Done. If response contains messages[].id (wamid...), outbound is OK."
