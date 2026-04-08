# wa-gateway Implementation Summary

Status: Operational reference
Audience: Backend / Infra
Last reviewed: 2026-04-08

**Date:** 2026-03-16  
**Status:** Active

## Scope
`wa-gateway` is a Go service that handles Meta WhatsApp Cloud API webhook ingress and outbound message delivery for TinkuBot AI services.

## Runtime Architecture
```
Meta WhatsApp Cloud API
    ↓ webhook
wa-gateway (Go + gin)
    ↓ HTTP webhook forwarding
AI services (ai-clientes, ai-proveedores)
```

## Active Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health |
| GET | `/meta/webhook` | Meta webhook verification |
| POST | `/meta/webhook` | Meta webhook event ingestion |
| POST | `/send` | Outbound WhatsApp send via Meta Cloud API |

Compatibility aliases under `/api` remain for `/send`.

## Environment Variables

Core:
- `GATEWAY_PORT` (default `7000`)
- `AI_CLIENTES_URL` (default `http://ai-clientes:8001`)
- `AI_PROVEEDORES_URL` (default `http://ai-proveedores:8002`)
- `WEBHOOK_ENDPOINT` (default `/handle-whatsapp-message`)

Rate limiting:
- `RATE_LIMIT_MAX_PER_HOUR` (default `20`)
- `RATE_LIMIT_MAX_PER_24H` (default `100`)

Meta:
- `WA_META_WEBHOOK_ENABLED`
- `WA_META_OUTBOUND_ENABLED`
- `WA_META_ENABLED_ACCOUNTS`
- `META_WEBHOOK_VERIFY_TOKEN`
- `META_APP_SECRET`
- `META_PHONE_NUMBER_ID_CLIENTES`
- `META_PHONE_NUMBER_ID_PROVEEDORES`
- `META_CLIENTES_ACCESS_TOKEN`
- `META_PROVEEDORES_ACCESS_TOKEN`

## Operational Checks
- Service health: `GET /health`
- Webhook verification path responds when enabled: `GET /meta/webhook`
- Outbound send path available: `POST /send`

## Known Limitations
1. Rate limits are in-memory and reset on restart.
2. Account mapping remains static in code (`bot-clientes`, `bot-proveedores`).
3. The service no longer manages WhatsApp Web sessions, QR login, or local device persistence.
