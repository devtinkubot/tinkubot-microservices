# wa-gateway Migration Summary

Status: Historical migration record
Audience: Backend / Infra
Last reviewed: 2026-04-08

## Overview
This document records the current state after removing the legacy `whatsmeow` transport and standardizing `wa-gateway` as a Meta Cloud API gateway only.

**Update date:** 2026-03-16

## Technology Change

| Component | Before | After |
|-----------|--------|-------|
| WhatsApp transport | `whatsmeow` + local device session | Meta WhatsApp Cloud API |
| Session persistence | Local SQLite / filesystem artifacts | None in repo |
| QR login flow | Supported | Removed |
| Outbound delivery | Mixed web session + Meta | Meta only |

## Current API Contract
- `GET /health`
- `GET /meta/webhook`
- `POST /meta/webhook`
- `POST /api/send`
- `POST /send`

## What Was Removed
- `GET /api/accounts`
- `GET /api/accounts/:id`
- `GET /api/accounts/:id/qr`
- `POST /api/accounts/:id/login`
- `POST /api/accounts/:id/logout`
- `GET /api/events/stream`
- Local runtime artifacts `wa-data/` and `wa-sessions/`

## Operational Notes
1. Inbound webhook forwarding to `ai-clientes` / `ai-proveedores` is unchanged.
2. Outbound sends still go through `POST /send`.
3. No QR-based reconnect or WhatsApp Web session recovery exists anymore.
