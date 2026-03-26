#!/usr/bin/env python3
"""Send a synthetic Meta inbound webhook to wa-gateway for BSUID/LID tests."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from urllib import error, request


def _strip_text(value: str | None) -> str:
    return (value or "").strip()


def _normalize_jid(value: str | None, default_server: str | None = None) -> str:
    texto = _strip_text(value)
    if not texto:
      return ""
    if "@" in texto:
        return texto
    digits = "".join(ch for ch in texto if ch.isdigit())
    if not digits:
        return texto
    server = _strip_text(default_server)
    if not server:
        return digits
    return f"{digits}@{server}"


def _build_signature(app_secret: str, body: bytes) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _contact_profile(args: argparse.Namespace) -> dict[str, str]:
    profile: dict[str, str] = {}
    for key in ("name", "formatted_name", "first_name", "last_name", "username", "country_code"):
        value = _strip_text(getattr(args, key))
        if value:
            profile[key] = value
    return profile


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    raw_from = _strip_text(args.from_number)
    from_user_id = _strip_text(args.from_user_id)
    contact_user_id = _strip_text(args.contact_user_id) or from_user_id

    from_value = _normalize_jid(raw_from, args.from_server)
    wa_id = _strip_text(args.wa_id)
    if not wa_id and from_value and "@" not in from_value:
        wa_id = from_value

    contact: dict[str, object] = {}
    profile = _contact_profile(args)
    if profile:
        contact["profile"] = profile

    if wa_id:
        contact["wa_id"] = wa_id
    if contact_user_id:
        contact["user_id"] = contact_user_id

    message: dict[str, object] = {
        "id": _strip_text(args.message_id),
        "timestamp": _strip_text(args.timestamp)
        or str(int(datetime.now(timezone.utc).timestamp())),
        "type": _strip_text(args.message_type),
    }
    if from_value:
        message["from"] = from_value
    if from_user_id:
        message["from_user_id"] = from_user_id

    if args.message_type == "text":
        message["text"] = {"body": args.body}
    elif args.message_type == "location":
        message["location"] = {
            "latitude": args.latitude,
            "longitude": args.longitude,
        }
        if args.location_name:
            message["location"]["name"] = args.location_name
        if args.location_address:
            message["location"]["address"] = args.location_address
    else:
        raise SystemExit(f"unsupported message_type: {args.message_type}")

    value: dict[str, object] = {
        "metadata": {"phone_number_id": args.phone_number_id},
        "messages": [message],
    }
    if contact:
        value["contacts"] = [contact]

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": args.waba_id,
                "changes": [
                    {
                        "field": "messages",
                        "value": value,
                    }
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a synthetic Meta inbound webhook to wa-gateway."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:7000/meta/webhook",
        help="Gateway webhook URL",
    )
    parser.add_argument(
        "--app-secret",
        default=os.getenv("WA_META_APP_SECRET", ""),
        help="Meta app secret used to sign the webhook body",
    )
    parser.add_argument(
        "--waba-id",
        default="waba-test",
        help="Meta business account id",
    )
    parser.add_argument(
        "--phone-number-id",
        required=True,
        help="Phone number id configured in wa-gateway",
    )
    parser.add_argument(
        "--from-number",
        default="",
        help="Inbound sender identifier. Use empty with --from-user-id to test BSUID-only",
    )
    parser.add_argument(
        "--from-server",
        default="",
        help="Optional server suffix when --from-number is raw digits, for example lid or s.whatsapp.net",
    )
    parser.add_argument(
        "--from-user-id",
        default="",
        help="BSUID to include as messages[0].from_user_id",
    )
    parser.add_argument(
        "--wa-id",
        default="",
        help="Explicit contact wa_id",
    )
    parser.add_argument(
        "--contact-user-id",
        default="",
        help="Explicit contact user_id. Defaults to --from-user-id when omitted",
    )
    parser.add_argument("--name", default="", help="Contact display name")
    parser.add_argument(
        "--formatted-name", default="", help="Contact formatted_name"
    )
    parser.add_argument("--first-name", default="", help="Contact first_name")
    parser.add_argument("--last-name", default="", help="Contact last_name")
    parser.add_argument("--username", default="", help="Contact username")
    parser.add_argument("--country-code", default="", help="Contact country_code")
    parser.add_argument(
        "--message-type",
        default="text",
        choices=("text", "location"),
        help="Synthetic message type",
    )
    parser.add_argument(
        "--body",
        default="hola",
        help="Text body for text messages",
    )
    parser.add_argument(
        "--message-id",
        default="wamid.test.1",
        help="Synthetic WhatsApp message id",
    )
    parser.add_argument(
        "--timestamp",
        default="",
        help="Unix timestamp. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=-0.180653,
        help="Latitude for location messages",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=-78.467834,
        help="Longitude for location messages",
    )
    parser.add_argument(
        "--location-name",
        default="Quito",
        help="Location name for location messages",
    )
    parser.add_argument(
        "--location-address",
        default="",
        help="Location address for location messages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload and signature without sending",
    )
    args = parser.parse_args()

    if not args.app_secret and not args.dry_run:
        print(
            "error: provide --app-secret or set WA_META_APP_SECRET to sign the payload",
            file=sys.stderr,
        )
        return 2

    payload = build_payload(args)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    signature = _build_signature(args.app_secret, body) if args.app_secret else ""

    print(f"URL: {args.url}")
    print(f"Phone number id: {args.phone_number_id}")
    print(f"From: {args.from_number or '(empty)'}")
    print(f"From user id: {args.from_user_id or '(empty)'}")
    print(f"Contact user id: {args.contact_user_id or args.from_user_id or '(empty)'}")
    print(f"Message type: {args.message_type}")
    print(body.decode("utf-8"))
    if signature:
        print(f"X-Hub-Signature-256: {signature}")

    if args.dry_run:
        return 0

    req = request.Request(
        args.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            print(response_body)
            return 0 if 200 <= resp.status < 300 else 1
    except error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return exc.code or 1
    except Exception as exc:  # pragma: no cover - best effort CLI
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
