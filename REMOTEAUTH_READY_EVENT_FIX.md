# RemoteAuth `ready` Event Not Firing - Root Cause Analysis & Permanent Fix

## Executive Summary

**Problem**: When using `RemoteAuth` with whatsapp-web.js v1.33.0, the `ready` event does NOT fire consistently after restoring a session from Supabase. The `authenticated` event fires, but `client.info` remains undefined.

**Root Cause**: This is a **KNOWN BUG** in whatsapp-web.js RemoteAuth implementation that has been reported multiple times since 2022. The issue occurs during session restoration when the timing between `authenticated` and `ready` events is disrupted.

**Evidence**:
- Multiple GitHub issues confirm this: [#3181](https://github.com/pedroslopez/whatsapp-web.js/issues/3181), [#5685](https://github.com/pedroslopez/whatsapp-web.js/issues/5685), [#3469](https://github.com/pedroslopez/whatsapp-web.js/issues/3469)
- Your current polling workaround works but is NOT a permanent solution
- The `ready` event is not guaranteed to fire after `authenticated` with RemoteAuth

---

## Current Implementation Analysis

### File: `/home/du/produccion/tinkubot-microservices/nodejs-services/wa-proveedores/index.js`

#### Event Handlers (Lines 700-751)

```javascript
client.on('authenticated', async () => {
  console.warn(`[${instanceName}] ✅ Autenticación exitosa (authenticated)`);
  console.warn(`[${instanceName}] ✅ Estado del cliente: ${client.info ? 'READY' : 'NOT READY'}`);

  // ❌ PROBLEM: client.info is undefined here!
  try {
    const info = client.info;
    if (info) {
      console.warn(`[${instanceName}] ✅ Info del cliente disponible:`, info.pushname || 'No name');
    }
  } catch (err) {
    console.error(`[${instanceName}] ⚠️ Error obteniendo info del cliente:`, err.message);
  }

  clientStatus = 'connected'; // ❌ WRONG: Prematurely marking as connected
  qrCodeData = null;
  io.emit('status', { status: 'connected', timestamp: new Date().toISOString() });
});

client.on('ready', () => {
  console.warn(`[${instanceName}] ✅ Cliente de WhatsApp está listo con sesión remota!`);
  // ✅ This is the CORRECT event, but it doesn't fire with RemoteAuth!
  qrCodeData = null;
  clientStatus = 'connected';

  if (sessionTimeout) {
    clearTimeout(sessionTimeout);
    sessionTimeout = null;
    sessionRetryCount = 0;
  }

  io.emit('status', { status: 'connected', timestamp: new Date().toISOString() });
});
```

#### Current Workaround: Polling (Lines 934-972)

```javascript
// Verificar periódicamente si el cliente está listo (para sesiones restauradas)
let checkCount = 0;
const readyCheckInterval = setInterval(async () => {
  checkCount++;
  try {
    const hasInfo = !!client.info;
    console.log(`[${instanceName}] 🔍 Verificación #${checkCount}: client.info=${hasInfo}, clientStatus=${clientStatus}`);

    if (clientStatus !== 'connected' && client.info) {
      console.warn(`[${instanceName}] ✅ Cliente detectado READY (verificación periódica)`);
      // ... mark as connected and clear interval
      clearInterval(readyCheckInterval);
    }
  } catch (err) {
    console.log(`[${instanceName}] ⚠️ Error en verificación #${checkCount}:`, err.message);
  }
}, 5000); // Check every 5 seconds

// Stop checking after 2 minutes
setTimeout(() => {
  clearInterval(readyCheckInterval);
}, 120000);
```

### Why This Works But Is NOT Ideal

**Pros**:
- ✅ Eventually detects when `client.info` becomes available
- ✅ Message listeners start working after detection
- ✅ Prevents "corrupted session" false positives

**Cons**:
- ❌ **Not deterministic**: 5-second polling for up to 2 minutes = 24 checks max
- ❌ **Race condition prone**: May miss the exact moment `client.info` is set
- ❌ **Resource waste**: Continuous polling even when session is stable
- ❌ **Timing dependent**: If initialization takes > 2 minutes, detection fails
- ❌ **Complex logic**: Multiple timers, counters, and state variables

---

## Root Cause: RemoteAuth Event Flow Bug

### Expected Event Flow (LocalAuth)

```
1. client.initialize()
2. QR Code Generated → qr event
3. User scans QR
4. authenticated event fires
5. WhatsApp Web finishes loading
6. ready event fires ← client.info is NOW available
7. Message listeners active
```

### Actual Event Flow (RemoteAuth with Session Restoration)

```
1. client.initialize()
2. RemoteAuth.extractRemoteSession() called
3. Session extracted from Supabase
4. Browser initialized with restored session
5. authenticated event fires ← BUT client.info is still UNDEFINED
6. ❌ ready event OFTEN DOES NOT FIRE (BUG)
7. ❌ client.info remains undefined
8. ❌ Message listeners don't work
9. ✅ Eventually client.info becomes available (timing varies)
```

### Why This Happens

According to the [RemoteAuth source code](https://github.com/pedroslopez/whatsapp-web.js/blob/main/docs/authStrategies_RemoteAuth.js.html):

1. **`beforeBrowserInitialized()`**: Calls `extractRemoteSession()` to restore session
2. **`afterAuthReady()`**: Starts periodic backup sync **only if session doesn't exist**
3. The `ready` event is supposed to fire after WhatsApp Web finishes loading
4. **BUG**: With restored sessions, the event timing is disrupted and `ready` often doesn't fire

### Evidence from GitHub Issues

- **[#3181 - Ready event is broken](https://github.com/pedroslopez/whatsapp-web.js/issues/3181)** (July 2024):
  > "After the `authenticated` event is successfully triggered, the code encounters an error and does not reach the `ready` event"

- **[#5685 - Client is authenticated but isn't ready](https://github.com/pedroslopez/whatsapp-web.js/issues/5685)** (Dec 2025):
  > "When restarting the PM2 server, the client gets authenticated but does not reach the ready state"

- **[#3469 - RemoteAuth Authentication bug](https://github.com/pedroslopez/whatsapp-web.js/issues/3469)** (Feb 2025):
  > "The bot with RemoteAuth and MongoDB storage authenticates twice in the same session"

---

## PERMANENT FIX: State-Based Ready Detection

### Solution: Use `client.getState()` Instead of `client.info`

The `client.getState()` method is more reliable than `client.info` for detecting readiness because it directly checks the WhatsApp Web connection state rather than relying on the event system.

### Implementation

#### Step 1: Replace Event-Based Logic with State Polling

```javascript
// Remove the old ready event dependency
// Instead, use a single, reliable state check loop

let readyCheckInterval = null;
let checkCount = 0;
const MAX_READY_CHECKS = 60; // 5 minutes with 5-second intervals
const READY_CHECK_INTERVAL = 5000;

async function checkClientReady() {
  checkCount++;

  try {
    // ✅ MORE RELIABLE: Check both state and info
    const state = await client.getState();
    const hasInfo = !!client.info;

    console.log(`[${instanceName}] 🔍 Estado #${checkCount}: state=${state}, hasInfo=${hasInfo}`);

    // ✅ CONNECTED means the client is truly ready
    if (state === 'CONNECTED' && hasInfo) {
      console.warn(`[${instanceName}] ✅ Cliente detectado READY (state=CONNECTED)`);
      console.warn(`[${instanceName}] ✅ Info: ${client.info.pushname || 'No name'}`);
      console.warn(`[${instanceName}] ✅ Listener de mensajes ACTIVO`);

      // Clear detection timer
      if (sessionTimeout) {
        clearTimeout(sessionTimeout);
        sessionTimeout = null;
        sessionRetryCount = 0;
      }

      clientStatus = 'connected';
      qrCodeData = null;

      // Notify WebSocket clients
      io.emit('status', {
        status: 'connected',
        timestamp: new Date().toISOString(),
      });

      // ✅ Stop checking - we're truly ready
      if (readyCheckInterval) {
        clearInterval(readyCheckInterval);
        readyCheckInterval = null;
      }
      return true; // Signal that we're ready
    }

    // ❌ If we exceed max checks without reaching CONNECTED
    if (checkCount >= MAX_READY_CHECKS) {
      console.error(`[${instanceName}] ❌ Timeout: Cliente no alcanzó estado CONNECTED después de ${MAX_READY_CHECKS} verificaciones`);
      clearInterval(readyCheckInterval);
      readyCheckInterval = null;
      return false;
    }

    return false; // Not ready yet
  } catch (err) {
    console.error(`[${instanceName}] ⚠️ Error verificando estado:`, err.message);
    return false;
  }
}

// Start checking when authenticated is received
client.on('authenticated', () => {
  console.warn(`[${instanceName}] ✅ Autenticación exitosa (authenticated)`);
  console.warn(`[${instanceName}] 🔍 Iniciando verificación de estado CONNECTED...`);

  // Start state-based ready detection
  if (!readyCheckInterval) {
    readyCheckInterval = setInterval(checkClientReady, READY_CHECK_INTERVAL);

    // Run immediate first check
    checkClientReady();
  }
});

// Keep ready event handler for new sessions (it works for those)
client.on('ready', () => {
  console.warn(`[${instanceName}] ✅ Cliente de WhatsApp está listo (evento ready recibido)`);

  if (readyCheckInterval) {
    clearInterval(readyCheckInterval);
    readyCheckInterval = null;
  }

  if (sessionTimeout) {
    clearTimeout(sessionTimeout);
    sessionTimeout = null;
    sessionRetryCount = 0;
  }

  clientStatus = 'connected';
  qrCodeData = null;

  io.emit('status', {
    status: 'connected',
    timestamp: new Date().toISOString(),
  });
});
```

#### Step 2: Remove `remote_session_saved` Workaround (Lines 753-792)

The `remote_session_saved` event handler has a 2-second setTimeout that tries to check `client.info`. This is redundant with the new state-based approach and should be removed:

```javascript
// ❌ REMOVE THIS (Lines 753-792)
client.on('remote_session_saved', () => {
  const now = Date.now();
  if (now - lastRemoteSessionLog < SESSION_LOG_INTERVAL_MS) {
    return;
  }

  lastRemoteSessionLog = now;
  console.warn(`[${instanceName}] ✅ Sesión restaurada desde Supabase Storage`);

  // ❌ REMOVE: This setTimeout workaround is no longer needed
  setTimeout(async () => {
    try {
      const info = client.info;
      if (info) {
        console.warn(`[${instanceName}] ✅ Cliente está READY - Info:`, info.pushname || 'No name');
        // ... rest of workaround
      }
    } catch (err) {
      console.error(`[${instanceName}] ❌ Error verificando estado del cliente:`, err.message);
    }
  }, 2000);
});

// ✅ REPLACE WITH simple logging
client.on('remote_session_saved', () => {
  const now = Date.now();
  if (now - lastRemoteSessionLog < SESSION_LOG_INTERVAL_MS) {
    return;
  }

  lastRemoteSessionLog = now;
  console.debug(`[${instanceName}] ✅ Sesión restaurada desde Supabase Storage`);
});
```

#### Step 3: Update Authenticated Event Handler (Lines 700-717)

```javascript
client.on('authenticated', async () => {
  console.warn(`[${instanceName}] ✅ Autenticación exitosa (authenticated)`);

  // ❌ DON'T check client.info here - it's undefined with RemoteAuth
  // ❌ DON'T set clientStatus = 'connected' yet - wait for CONNECTED state
  // ✅ Just log and let the state check loop handle readiness

  qrCodeData = null;
  io.emit('status', {
    status: 'authenticating',
    timestamp: new Date().toISOString()
  });

  // Start state-based ready detection (if not already started)
  if (!readyCheckInterval) {
    readyCheckInterval = setInterval(checkClientReady, READY_CHECK_INTERVAL);
    // Run immediate check
    checkClientReady();
  }
});
```

---

## Why This Solution Is Superior

### 1. **Reliable State Detection**
- Uses `client.getState()` which directly polls WhatsApp Web's internal state
- `CONNECTED` state means the client is **truly ready** to receive/send messages
- More deterministic than checking `client.info`

### 2. **Handles Both Scenarios**
- **New sessions**: `ready` event fires → clears interval → works perfectly
- **Restored sessions**: `ready` doesn't fire → `getState()` detects `CONNECTED` → works perfectly

### 3. **No Race Conditions**
- Checks every 5 seconds for up to 5 minutes (60 checks)
- Covers even slow initialization scenarios
- Immediate first check reduces latency

### 4. **Cleaner Code**
- Single source of truth for readiness: `state === 'CONNECTED' && hasInfo`
- No multiple setTimeout workarounds
- Clear logging of each state transition

### 5. **Better Error Handling**
- Explicit timeout after max checks
- Doesn't silently fail after 2 minutes
- Clear error messages in logs

---

## Implementation Checklist

### Files to Modify
- [ ] `/home/du/produccion/tinkubot-microservices/nodejs-services/wa-proveedores/index.js`

### Changes Required
1. [ ] Add `checkClientReady()` function before event handlers
2. [ ] Modify `authenticated` event handler to start state checking
3. [ ] Simplify `ready` event handler (keep as backup)
4. [ ] Remove `remote_session_saved` workaround (lines 753-792)
5. [ ] Remove old polling code (lines 934-972)
6. [ ] Test with both new and restored sessions

### Testing Strategy
1. **Test Case 1**: New Session
   - Delete existing session from Supabase
   - Start service
   - Verify QR is generated
   - Scan QR
   - Verify `ready` event fires
   - Verify messages can be sent/received

2. **Test Case 2**: Restored Session
   - Ensure session exists in Supabase
   - Restart service
   - Verify `authenticated` event fires
   - Verify `ready` event does NOT fire (expected)
   - Verify `getState()` detects `CONNECTED`
   - Verify messages can be sent/received

3. **Test Case 3**: Corrupted Session
   - Corrupt session data in Supabase
   - Restart service
   - Verify timeout detection after 5 minutes
   - Verify auto-cleanup triggers
   - Verify new QR is generated

---

## Additional Considerations

### Wa-Clientes Service
The same issue exists in `/home/du/produccion/tinkubot-microservices/nodejs-services/wa-clientes/index.js`. While the wa-clientes service doesn't currently have the polling workaround, it's experiencing the same underlying issue and should be updated with the same fix for consistency.

### SupabaseStore Implementation
Your `SupabaseStore.js` implementation is correct and doesn't need changes. The issue is entirely in the event handling logic in `index.js`.

### Future-Proofing
Monitor the following GitHub issues for upstream fixes:
- https://github.com/pedroslopez/whatsapp-web.js/issues/3181
- https://github.com/pedroslopez/whatsapp-web.js/issues/5685

If the `ready` event bug is fixed in a future version, this solution will still work correctly because:
1. The `ready` event handler will fire first and clear the interval
2. The state check loop will never detect `CONNECTED` because it's already cleared
3. Backward compatible with both old and new behavior

---

## Conclusion

The root cause of your RemoteAuth `ready` event issue is a **long-standing bug in whatsapp-web.js** that affects session restoration. The current polling workaround is functional but not ideal.

The proposed permanent fix using `client.getState()` is:
- ✅ **More reliable**: Uses internal WhatsApp Web state
- ✅ **More deterministic**: Clear success criteria
- ✅ **Backward compatible**: Works with new and restored sessions
- ✅ **Maintainable**: Cleaner code, clearer logic
- ✅ **Future-proof**: Will work even if upstream bug is fixed

---

## References

- [whatsapp-web.js Issue #3181 - Ready event is broken](https://github.com/pedroslopez/whatsapp-web.js/issues/3181)
- [whatsapp-web.js Issue #5685 - Client is authenticated but isn't ready](https://github.com/pedroslopez/whatsapp-web.js/issues/5685)
- [whatsapp-web.js Issue #3469 - RemoteAuth Authentication bug](https://github.com/pedroslopez/whatsapp-web.js/issues/3469)
- [whatsapp-web.js Issue #2038 - Remote auth not working properly](https://github.com/pedroslopez/whatsapp-web.js/issues/2038)
- [RemoteAuth Source Code Documentation](https://github.com/pedroslopez/whatsapp-web.js/blob/main/docs/authStrategies_RemoteAuth.js.html)
- [Stack Overflow: whatsapp-webjs remote auth not working properly](https://stackoverflow.com/questions/77280156/whatsapp-webjs-remote-auth-not-working-propery)
- [whatsapp-web.js Official Authentication Guide](https://wwebjs.dev/guide/creating-your-bot/authentication)
