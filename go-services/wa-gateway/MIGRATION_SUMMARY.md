# wa-gateway Migration Summary: Node.js -> Go + whatsmeow + SQLite

## Overview
This document records the migration from Node.js/Baileys to Go/whatsmeow and clarifies the current production-like behavior.

**Migration date:** 2026-01-30  
**Clarification update:** 2026-02-19

---

## Technology Change
| Component | Before | After |
|-----------|--------|-------|
| Language | Node.js (TypeScript) | Go |
| WA library | Baileys | whatsmeow |
| Session persistence | Filesystem/session artifacts | SQLite via whatsmeow sqlstore |
| Rate limiting | DB-backed design (legacy intent) | In-memory limiter |

---

## Current State (As-Built)
1. `wa-gateway` persists WhatsApp session/state in local SQLite (`wa-gateway.db`) through `whatsmeow` sqlstore.
2. The database currently contains `whatsmeow_*` tables managed by the library.
3. Rate limiting is implemented in memory and is not persisted.
4. Account metadata exposed by API is derived from service code and live client state.

## What This Means
- SQLite persistence is real and active for WhatsApp sessions.
- A container restart preserves `whatsmeow` session data as long as `wa-data` volume persists.
- Rate-limit counters reset on restart.

---

## API Contract (unchanged)
- `GET /health`
- `GET /api/accounts`
- `GET /api/accounts/:id`
- `GET /api/accounts/:id/qr`
- `POST /api/accounts/:id/login`
- `POST /api/accounts/:id/logout`
- `POST /api/send`
- `GET /api/events/stream`

(Compatibility aliases without `/api` are still exposed.)

---

## Data Persistence Checklist
- [ ] `./wa-data/wa-gateway.db` exists
- [ ] Service restarts without forcing QR re-link when sessions already exist
- [ ] `GET /api/accounts` reflects expected status transitions

## Runtime Verification Commands
```bash
# DB file exists on host
ls -lh ./wa-data/wa-gateway.db

# Service health
curl http://localhost:7000/health

# Account states
curl http://localhost:7000/api/accounts
```

---

## Limitations
1. Rate limiting is not persisted.
2. Account inventory is static (`bot-clientes`, `bot-proveedores`).
3. No built-in historical message store in this service.

---

## Rollback Reminder
If needed, rollback is done at git/deployment level (restore previous service implementation and compose wiring).

---

## References
- `go-services/wa-gateway/cmd/wa-gateway/main.go`
- `go-services/wa-gateway/internal/whatsmeow/client_manager.go`
- `go-services/wa-gateway/internal/ratelimit/limiter.go`
- `go-services/wa-gateway/internal/api/handlers.go`
