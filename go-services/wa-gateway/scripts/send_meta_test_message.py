#!/usr/bin/env python3
"""Send a WhatsApp Cloud API test message from inside wa-gateway container."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        # Ecuador local format -> E.164 without plus
        return "593" + digits[1:]
    return digits


def build_command(payload: str, container: str, account: str) -> list[str]:
    shell_cmd = (
        "set -euo pipefail; "
        'case "${ACCOUNT_ID}" in '
        '  "bot-clientes") '
        '    PHONE_NUMBER_ID="${META_PHONE_NUMBER_ID_CLIENTES:-}"; '
        '    ACCESS_TOKEN="${META_CLIENTES_ACCESS_TOKEN:-}"; '
        '    ;; '
        '  "bot-proveedores") '
        '    PHONE_NUMBER_ID="${META_PHONE_NUMBER_ID_PROVEEDORES:-}"; '
        '    ACCESS_TOKEN="${META_PROVEEDORES_ACCESS_TOKEN:-}"; '
        '    ;; '
        '  *) '
        '    echo "unsupported ACCOUNT_ID=${ACCOUNT_ID}" >&2; '
        '    exit 1; '
        '    ;; '
        'esac; '
        ': "${PHONE_NUMBER_ID:?phone number id missing}"; '
        ': "${ACCESS_TOKEN:?access token missing}"; '
        'API_VERSION="${META_GRAPH_API_VERSION:-v25.0}"; '
        'URL="https://graph.facebook.com/${API_VERSION}/${PHONE_NUMBER_ID}/messages"; '
        'if command -v curl >/dev/null 2>&1; then '
        '  curl -sS -X POST '
        '    -H "Authorization: Bearer ${ACCESS_TOKEN}" '
        '    -H "Content-Type: application/json" '
        '    --data "${PAYLOAD}" '
        '    "${URL}"; '
        'else '
        '  wget -qO- '
        '    --header="Authorization: Bearer ${ACCESS_TOKEN}" '
        '    --header="Content-Type: application/json" '
        '    --post-data="${PAYLOAD}" '
        '    "${URL}"; '
        'fi'
    )
    return [
        "docker",
        "exec",
        "-e",
        f"ACCOUNT_ID={account}",
        "-e",
        f"PAYLOAD={payload}",
        container,
        "/bin/sh",
        "-lc",
        shell_cmd,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Meta Cloud API test message from wa-gateway container.")
    parser.add_argument("--container", default="tinkubot-wa-gateway", help="Docker container name")
    parser.add_argument("--account", default="bot-clientes", help="Gateway account id: bot-clientes or bot-proveedores")
    parser.add_argument("--to", default="0959091325", help="Destination phone number")
    parser.add_argument(
        "--message",
        default="prueba de curl desde wa-gateway",
        help="Message body",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing")
    args = parser.parse_args()

    to = normalize_phone(args.to)
    if not to:
        print("error: destination phone is empty after normalization", file=sys.stderr)
        return 2

    payload = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": args.message},
        },
        ensure_ascii=False,
    )

    command = build_command(payload, args.container, args.account)

    print(f"Container: {args.container}")
    print(f"Account: {args.account}")
    print(f"To: {to}")
    print(f"Message: {args.message}")
    if args.dry_run:
        print("Dry run command:")
        print(" ".join(command))
        return 0

    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
