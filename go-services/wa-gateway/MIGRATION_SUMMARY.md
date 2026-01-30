# wa-gateway Migration Summary: Node.js → Go with SQLite

## Overview
Successfully migrated wa-gateway from Node.js + Baileys to Go + whatsmeow + SQLite.

## Date
2026-01-30

## What Changed

### Technology Stack
| Component | Before | After |
|-----------|--------|-------|
| Language | Node.js (TypeScript) | Go 1.21 |
| Library | @whiskeysockets/baileys v6.7.0 | go.mau.fi/whatsmeow |
| Storage | File system (sessions/) | SQLite database (wa-gateway.db) |
| Rate Limiting | Supabase PostgreSQL | In-memory (map) |
| Docker Image | ~150MB (Node.js) | ~300MB (Go with CGO) |

### Key Changes

#### 1. Database Migration
**Before:**
- PostgreSQL (Supabase) for session state
- Tables: `wa_accounts`, `wa_account_states`, `wa_rate_limits`
- Required `DATABASE_URL` environment variable

**After:**
- SQLite local database for session storage only
- Single file: `./data/wa-gateway.db`
- No external database dependency
- Environment variable: `DATABASE_PATH` (optional, defaults to `file:./data/wa-gateway.db?_foreign_keys=on`)

#### 2. Rate Limiting
**Before:**
```go
// PostgreSQL-based
func (rl *Limiter) Check(ctx context.Context, accountID, destinationPhone string) (bool, error) {
    // Query wa_rate_limits table
}
```

**After:**
```go
// In-memory
type Limiter struct {
    mu     sync.RWMutex
    store  map[string]*RateLimitEntry
    config Config
}
```

**Limitations:**
- Rate limits reset on container restart
- No persistence across restarts
- Trade-off: Simplicity vs persistence

#### 3. Client Management
**Before:**
- Required PostgreSQL connection pool
- Account metadata stored in database

**After:**
- No database required for client operations
- Account metadata hardcoded (bot-clientes, bot-proveedores)
- Connection status from whatsmeow client directly

#### 4. API Changes
**Before:**
```bash
GET /api/accounts  # Returns accounts from database
```

**After:**
```bash
GET /api/accounts  # Returns hardcoded accounts + live connection status
```

**API Endpoints (unchanged):**
- `GET /health`
- `GET /api/accounts`
- `GET /api/accounts/:id`
- `GET /api/accounts/:id/qr`
- `POST /api/accounts/:id/login`
- `POST /api/accounts/:id/logout`
- `POST /api/send`
- `GET /api/events/stream`

### File Structure

**Deleted:**
```
nodejs-services/wa-gateway/
├── package.json
├── Dockerfile
├── tsconfig.json
├── BUGS_AND_FIXES.md
└── src/
    ├── index.ts
    ├── server.ts
    ├── whatsapp/
    │   ├── client-manager.ts
    │   ├── auth-storage.ts
    │   └── rate-limiter.ts
    └── api/
        ├── routes.ts
        └── handlers.ts
```

**Modified:**
```
go-services/wa-gateway/
├── cmd/wa-gateway/
│   └── main.go                 # Removed PostgreSQL, added SQLite
├── internal/
│   ├── api/
│   │   └── handlers.go         # Removed DB queries, hardcoded accounts
│   ├── whatsmeow/
│   │   └── client_manager.go   # Removed PostgreSQL, SQLite only
│   └── ratelimit/
│       └── limiter.go          # PostgreSQL → In-memory map
├── go.mod                      # pgx → go-sqlite3
├── go.sum
└── Dockerfile                  # CGO_ENABLED=1 for SQLite
```

### Docker Configuration

**docker-compose.yml Changes:**
```yaml
# Before
wa-gateway:
  build:
    context: ./nodejs-services/wa-gateway
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - SUPABASE_URL=${SUPABASE_URL}
  volumes:
    - ./wa-sessions:/app/src/sessions

# After
wa-gateway:
  build:
    context: ./go-services/wa-gateway
  environment:
    - DATABASE_PATH=file:./data/wa-gateway.db?_foreign_keys=on
  volumes:
    - ./wa-data:/app/data  # For SQLite .db file
```

## Why This Migration?

### Problem with Node.js + Baileys
- **Error 405**: WhatsApp rejecting connections with Baileys v6.7.0
- **Downgrade risk**: No guarantee v6.5.0 would fix it
- **Stability issues**: Baileys less stable than whatsmeow

### Benefits of Go + whatsmeow + SQLite
1. **✅ Proven technology**: whatsmeow worked before with the same IP
2. **✅ Simple storage**: SQLite = single file, no containers needed
3. **✅ More stable**: Maintained by same author as Baileys (@tulir)
4. **✅ No external deps**: No Supabase required for sessions
5. **✅ Small overhead**: Rate limiting in-memory is sufficient

## Testing Checklist

### Build & Deploy
- [ ] `docker-compose build wa-gateway` succeeds
- [ ] Image size ~300MB (expected with CGO)
- [ ] Container starts without errors

### Database
- [ ] SQLite file created: `./wa-data/wa-gateway.db`
- [ ] File persists after container restart
- [ ] No PostgreSQL connection errors in logs

### WhatsApp Connection
- [ ] QR code generated without error 405
- [ ] QR scannable from WhatsApp mobile
- [ ] Connection status changes to "connected"
- [ ] Session persists after container restart

### API Endpoints
- [ ] `GET /health` returns 200
- [ ] `GET /api/accounts` returns both bot accounts
- [ ] `POST /api/accounts/bot-clientes/login` generates QR
- [ ] `POST /api/send` sends messages successfully

### Rate Limiting
- [ ] 20 messages/hour limit enforced
- [ ] 100 messages/day limit enforced
- [ ] Retry-After header returned when limited

### Frontend Integration
- [ ] Admin dashboard accessible at `:5000/admin-dashboard.html`
- [ ] QR codes display correctly
- [ ] Connection status updates in real-time
- [ ] No console errors

## Known Limitations

### 1. Rate Limiting
**Limitation:** Resets on container restart
**Impact:** Users can send 20 messages immediately after restart
**Mitigation:** Acceptable trade-off for simplicity
**Future:** Can add persistence if needed

### 2. Account Management
**Limitation:** Accounts hardcoded (bot-clientes, bot-proveedores)
**Impact:** Cannot dynamically add accounts via API
**Mitigation:** Only 2 accounts needed for this project
**Future:** Can add config file if more accounts needed

### 3. Message History
**Limitation:** No message history stored
**Impact:** Cannot view past messages in dashboard
**Mitigation:** Not a requirement for current use case
**Future:** Can add SQLite table for message logs if needed

## Rollback Plan

If issues arise:

```bash
# 1. Stop current service
docker-compose stop wa-gateway

# 2. Restore Node.js version from git
git checkout d343a75 -- nodejs-services/wa-gateway/

# 3. Restore docker-compose.yml
git checkout d343a75 -- docker-compose.yml

# 4. Rebuild and start
docker-compose build wa-gateway
docker-compose up -d wa-gateway
```

## Next Steps

1. **Test thoroughly** using the checklist above
2. **Monitor logs** for any WhatsApp connection issues
3. **Verify frontend** integration works correctly
4. **Consider backups** of `./wa-data/wa-gateway.db` file

## References

- [whatsmeow GitHub](https://github.com/tulir/whatsmeow)
- [whatsmeow sqlstore documentation](https://pkg.go.dev/go.mau.fi/whatsmeow/store/sqlstore)
- [go-sqlite3 documentation](https://github.com/mattn/go-sqlite3)

## Support

For issues or questions:
1. Check logs: `docker logs -f tinkubot-wa-gateway`
2. Verify SQLite file: `ls -lh ./wa-data/wa-gateway.db`
3. Test connection: `curl http://localhost:7000/health`
4. Check WhatsApp status: `curl http://localhost:7000/api/accounts`
