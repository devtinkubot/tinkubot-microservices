-- ============================================================================
-- Migration: wa-gateway initial schema
-- Date: 2026-01-30
-- Description: Create tables for wa-gateway service (Go + whatsmeow)
-- ============================================================================

-- ============================================================================
-- FUNCTION: update_updated_at_column()
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- TABLE: wa_accounts
-- Description: Registry of WhatsApp accounts (only 2 records: bot-clientes, bot-proveedores)
-- ============================================================================
CREATE TABLE IF NOT EXISTS wa_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('clientes', 'proveedores')),
    webhook_url TEXT NOT NULL,
    display_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trigger_wa_accounts_updated_at
    BEFORE UPDATE ON wa_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wa_accounts_account_id ON wa_accounts(account_id);
CREATE INDEX IF NOT EXISTS idx_wa_accounts_account_type ON wa_accounts(account_type);


-- ============================================================================
-- TABLE: wa_account_states
-- Description: Connection state per account (QR, connected, disconnected, etc)
-- ============================================================================
CREATE TABLE IF NOT EXISTS wa_account_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) UNIQUE NOT NULL REFERENCES wa_accounts(account_id) ON DELETE CASCADE,
    connection_status VARCHAR(50) NOT NULL DEFAULT 'disconnected'
        CHECK (connection_status IN ('disconnected', 'connecting', 'qr_ready', 'connected', 'error')),
    qr_code TEXT,
    qr_expires_at TIMESTAMPTZ,
    phone_number VARCHAR(20),
    connected_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    last_error TEXT,
    messages_received INTEGER DEFAULT 0,
    messages_sent INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trigger_wa_account_states_updated_at
    BEFORE UPDATE ON wa_account_states
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wa_account_states_account_id ON wa_account_states(account_id);
CREATE INDEX IF NOT EXISTS idx_wa_account_states_connection_status ON wa_account_states(connection_status);


-- ============================================================================
-- TABLE: wa_rate_limits
-- Description: Rate limiting per account/destination (20/hour, 100/24h)
-- ============================================================================
CREATE TABLE IF NOT EXISTS wa_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) NOT NULL REFERENCES wa_accounts(account_id) ON DELETE CASCADE,
    destination_phone VARCHAR(20) NOT NULL,
    messages_last_hour INTEGER DEFAULT 0,
    messages_last_24h INTEGER DEFAULT 0,
    window_start_timetz TIMESTAMPTZ DEFAULT NOW(),
    window_24h_start_timetz TIMESTAMPTZ DEFAULT NOW(),
    is_blocked BOOLEAN DEFAULT false,
    blocked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT wa_rate_limits_unique UNIQUE (account_id, destination_phone)
);

CREATE TRIGGER trigger_wa_rate_limits_updated_at
    BEFORE UPDATE ON wa_rate_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wa_rate_limits_account_destination ON wa_rate_limits(account_id, destination_phone);
CREATE INDEX IF NOT EXISTS idx_wa_rate_limits_window_start ON wa_rate_limits(window_start_timetz);
CREATE INDEX IF NOT EXISTS idx_wa_rate_limits_window_24h ON wa_rate_limits(window_24h_start_timetz);


-- ============================================================================
-- SEED DATA: Insert 2 default accounts
-- ============================================================================
INSERT INTO wa_accounts (account_id, account_type, webhook_url, display_name)
VALUES
    ('bot-clientes', 'clientes', 'http://ai-clientes:8001/handle-whatsapp-message', 'TinkuBot Clientes'),
    ('bot-proveedores', 'proveedores', 'http://ai-proveedores:8002/handle-whatsapp-message', 'TinkuBot Proveedores')
ON CONFLICT (account_id) DO NOTHING;

INSERT INTO wa_account_states (account_id, connection_status)
VALUES ('bot-clientes', 'disconnected'), ('bot-proveedores', 'disconnected')
ON CONFLICT (account_id) DO NOTHING;


-- ============================================================================
-- NOTES:
-- ============================================================================
-- whatsmeow will create its own tables automatically when initialized:
-- - whatsmeow_sessions
-- - whatsmeow_device_keys
-- - whatsmeow_identity_keys
-- - whatsmeow_app_state_sync_keys
-- - whatsmeow_app_state
--
-- Do NOT create these tables manually; let whatsmeow's sqlstore handle them.
-- ============================================================================
