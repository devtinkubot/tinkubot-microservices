# wa-gateway Implementation Summary

**Date:** 2026-01-30  
**Last updated:** 2026-02-19  
**Status:** Active

---

## Scope
This service runs WhatsApp connectivity with Go + `whatsmeow`, exposes HTTP/SSE APIs, and forwards inbound messages to AI services by webhook.

## Current Runtime Architecture

```
Frontend (Node.js)
    ↓ HTTP/SSE
wa-gateway (Go + gin + whatsmeow)
    ↓ HTTP webhooks
AI services (ai-clientes, ai-proveedores)

Persistence used by wa-gateway:
- SQLite file: ./wa-data/wa-gateway.db (mounted from ./wa-data -> /app/data)
- Content: whatsmeow-managed tables (session/device/app-state)
```

## Important Clarification About SQLite Usage
`wa-gateway` uses SQLite through `whatsmeow` sqlstore for WhatsApp session/state persistence.

As of this update:
- Runtime uses `whatsmeow_*` tables only.
- Rate limiting is in-memory (`internal/ratelimit/limiter.go`) and resets on restart.
- Account metadata is handled in code (known accounts), not from custom DB tables.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health |
| GET | `/accounts` | List accounts with live status |
| GET | `/accounts/:accountId` | Account details |
| GET | `/accounts/:accountId/qr` | Current QR if available |
| POST | `/accounts/:accountId/login` | Generate/regenerate QR |
| POST | `/accounts/:accountId/logout` | Logout/disconnect |
| POST | `/send` | Send WhatsApp message (rate-limited) |
| GET | `/events/stream` | SSE stream for realtime events |

Compatibility aliases without `/api` are also exposed by `main.go`.

## Environment Variables

Core:
- `GATEWAY_PORT` (default `7000`)
- `DATABASE_PATH` (default `file:./data/wa-gateway.db?_foreign_keys=on`)
- `AI_CLIENTES_URL` (default `http://ai-clientes:8001`)
- `AI_PROVEEDORES_URL` (default `http://ai-proveedores:8002`)
- `WEBHOOK_ENDPOINT` (default `/handle-whatsapp-message`)

Rate limiting:
- `RATE_LIMIT_MAX_PER_HOUR` (default `20`)
- `RATE_LIMIT_MAX_PER_24H` (default `100`)

Optional device pinning:
- `WA_CLIENTES_DEVICE_JID`
- `WA_PROVEEDORES_DEVICE_JID`

## Deployment Notes
- Build: `docker compose build wa-gateway`
- Run: `docker compose up -d wa-gateway`
- Persisted data path: `./wa-data/wa-gateway.db`

## Operational Checks
- Service health: `GET /health`
- Accounts state: `GET /api/accounts`
- SQLite file present and growing: `./wa-data/wa-gateway.db`

## Known Limitations
1. Rate limits are in-memory and reset on restart.
2. Account registry is static in code (`bot-clientes`, `bot-proveedores`).
3. No message history table in `wa-gateway`.

## References
- `go-services/wa-gateway/cmd/wa-gateway/main.go`
- `go-services/wa-gateway/internal/whatsmeow/client_manager.go`
- `go-services/wa-gateway/internal/ratelimit/limiter.go`
- `go-services/wa-gateway/internal/api/handlers.go`
