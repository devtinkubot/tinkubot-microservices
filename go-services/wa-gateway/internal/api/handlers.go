package api

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/tinkubot/wa-gateway/internal/ratelimit"
	"github.com/tinkubot/wa-gateway/internal/whatsmeow"
)

// Handlers holds the dependencies for HTTP handlers
type Handlers struct {
	db            *pgxpool.Pool
	clientManager *whatsmeow.ClientManager
	rateLimiter   *ratelimit.Limiter
	sseHub        *SSEHub
}

// NewHandlers creates a new Handlers instance
func NewHandlers(db *pgxpool.Pool, cm *whatsmeow.ClientManager, rl *ratelimit.Limiter, sseHub *SSEHub) *Handlers {
	return &Handlers{
		db:            db,
		clientManager: cm,
		rateLimiter:   rl,
		sseHub:        sseHub,
	}
}

// Account represents an account with its state
type Account struct {
	ID               string    `json:"id"`
	AccountID        string    `json:"account_id"`
	PhoneNumber      string    `json:"phone_number,omitempty"`
	AccountType      string    `json:"account_type"`
	WebhookURL       string    `json:"webhook_url"`
	DisplayName      string    `json:"display_name"`
	ConnectionStatus string    `json:"connection_status"`
	QRCode           string    `json:"qr_code,omitempty"`
	QRExpiresAt      *time.Time `json:"qr_expires_at,omitempty"`
	ConnectedAt      *time.Time `json:"connected_at,omitempty"`
	LastSeenAt       *time.Time `json:"last_seen_at,omitempty"`
	MessagesReceived int       `json:"messages_received"`
	MessagesSent     int       `json:"messages_sent"`
	IsActive         bool      `json:"is_active"`
}

// GetHealth returns health check information
func (h *Handlers) GetHealth(c *gin.Context) {
	ctx := context.Background()

	// Check Postgres connection
	var pgStatus string
	var pgLatency int64
	pgStart := time.Now()
	err := h.db.Ping(ctx)
	pgLatency = time.Since(pgStart).Milliseconds()

	if err != nil {
		pgStatus = "unhealthy"
	} else {
		pgStatus = "healthy"
	}

	// Count connected accounts
	var connectedCount int
	var totalCount int
	h.db.QueryRow(ctx, "SELECT COUNT(*) FROM wa_account_states WHERE connection_status = 'connected'").Scan(&connectedCount)
	h.db.QueryRow(ctx, "SELECT COUNT(*) FROM wa_accounts").Scan(&totalCount)

	c.JSON(http.StatusOK, gin.H{
		"status":            "healthy",
		"service":           "wa-gateway",
		"version":           "1.0.0",
		"uptime_seconds":    0, // TODO: track actual uptime
		"timestamp":         time.Now().Format(time.RFC3339),
		"accounts_total":    totalCount,
		"accounts_connected": connectedCount,
		"dependencies": gin.H{
			"postgres": gin.H{
				"status":      pgStatus,
				"latency_ms":  pgLatency,
			},
		},
	})
}

// GetAccounts returns all accounts with their connection status
func (h *Handlers) GetAccounts(c *gin.Context) {
	ctx := context.Background()

	// Join wa_accounts with wa_account_states
	rows, err := h.db.Query(ctx, `
		SELECT
			a.id,
			a.account_id,
			a.phone_number,
			a.account_type,
			a.webhook_url,
			a.display_name,
			s.connection_status,
			s.qr_code,
			s.qr_expires_at,
			s.connected_at,
			s.last_seen_at,
			s.messages_received,
			s.messages_sent
		FROM wa_accounts a
		LEFT JOIN wa_account_states s ON a.account_id = s.account_id
		ORDER BY a.account_id
	`)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to query accounts",
			"message": err.Error(),
		})
		return
	}
	defer rows.Close()

	accounts := []Account{}
	for rows.Next() {
		var acc Account
		var qrCode *string
		var qrExpiresAt *time.Time
		var connectedAt *time.Time
		var lastSeenAt *time.Time
		var phoneNumber *string

		err := rows.Scan(
			&acc.ID,
			&acc.AccountID,
			&phoneNumber,
			&acc.AccountType,
			&acc.WebhookURL,
			&acc.DisplayName,
			&acc.ConnectionStatus,
			&qrCode,
			&qrExpiresAt,
			&connectedAt,
			&lastSeenAt,
			&acc.MessagesReceived,
			&acc.MessagesSent,
		)
		if err != nil {
			continue
		}

		if phoneNumber != nil {
			acc.PhoneNumber = *phoneNumber
		}
		if qrCode != nil {
			acc.QRCode = *qrCode
		}
		acc.QRExpiresAt = qrExpiresAt
		acc.ConnectedAt = connectedAt
		acc.LastSeenAt = lastSeenAt
		acc.IsActive = true // All accounts in DB are active

		accounts = append(accounts, acc)
	}

	c.JSON(http.StatusOK, accounts)
}

// GetAccount returns a single account by ID
func (h *Handlers) GetAccount(c *gin.Context) {
	accountID := c.Param("accountId")

	ctx := context.Background()

	var acc Account
	var qrCode *string
	var qrExpiresAt *time.Time
	var connectedAt *time.Time
	var lastSeenAt *time.Time
	var phoneNumber *string

	err := h.db.QueryRow(ctx, `
		SELECT
			a.id,
			a.account_id,
			a.phone_number,
			a.account_type,
			a.webhook_url,
			a.display_name,
			s.connection_status,
			s.qr_code,
			s.qr_expires_at,
			s.connected_at,
			s.last_seen_at,
			s.messages_received,
			s.messages_sent
		FROM wa_accounts a
		LEFT JOIN wa_account_states s ON a.account_id = s.account_id
		WHERE a.account_id = $1
	`, accountID).Scan(
		&acc.ID,
		&acc.AccountID,
		&phoneNumber,
		&acc.AccountType,
		&acc.WebhookURL,
		&acc.DisplayName,
		&acc.ConnectionStatus,
		&qrCode,
		&qrExpiresAt,
		&connectedAt,
		&lastSeenAt,
		&acc.MessagesReceived,
		&acc.MessagesSent,
	)

	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Account not found",
			"message": "No account found with ID " + accountID,
			"code": "ACCOUNT_NOT_FOUND",
		})
		return
	}

	if phoneNumber != nil {
		acc.PhoneNumber = *phoneNumber
	}
	if qrCode != nil {
		acc.QRCode = *qrCode
	}
	acc.QRExpiresAt = qrExpiresAt
	acc.ConnectedAt = connectedAt
	acc.LastSeenAt = lastSeenAt
	acc.IsActive = true

	c.JSON(http.StatusOK, acc)
}

// GetQR returns the QR code for an account
func (h *Handlers) GetQR(c *gin.Context) {
	accountID := c.Param("accountId")
	format := c.DefaultQuery("format", "json")

	ctx := context.Background()

	var status string
	var qrCode *string
	var qrExpiresAt *time.Time

	err := h.db.QueryRow(ctx, `
		SELECT connection_status, qr_code, qr_expires_at
		FROM wa_account_states
		WHERE account_id = $1
	`, accountID).Scan(&status, &qrCode, &qrExpiresAt)

	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Account not found",
		})
		return
	}

	if status != "qr_ready" || qrCode == nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "QR not available",
			"message": "Account is already connected or not initialized",
		})
		return
	}

	if format == "image" {
		// TODO: Generate actual PNG image from QR code
		// For now, return JSON
		c.JSON(http.StatusOK, gin.H{
			"account_id": accountID,
			"qr_code": *qrCode,
			"generated_at": time.Now().Format(time.RFC3339),
			"expires_at": qrExpiresAt.Format(time.RFC3339),
			"note": "Image format not yet implemented, use json format",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"account_id": accountID,
		"qr_code": *qrCode,
		"generated_at": time.Now().Format(time.RFC3339),
		"expires_at": qrExpiresAt.Format(time.RFC3339),
		"instructions": "Abre WhatsApp > Ajustes > Dispositivos vinculados > Vincular",
	})
}

// PostLogin initiates or regenerates QR code for an account
func (h *Handlers) PostLogin(c *gin.Context) {
	accountID := c.Param("accountId")

	var req struct {
		Force bool `json:"force"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		// Allow empty body
		req.Force = false
	}

	// Check if account exists
	ctx := context.Background()
	var exists bool
	h.db.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM wa_accounts WHERE account_id = $1)", accountID).Scan(&exists)

	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Account not found",
			"message": "No account found with ID " + accountID,
		})
		return
	}

	// Get current status
	var status string
	h.db.QueryRow(ctx, "SELECT connection_status FROM wa_account_states WHERE account_id = $1", accountID).Scan(&status)

	if status == "connected" && !req.Force {
		c.JSON(http.StatusConflict, gin.H{
			"error": "Already connected",
			"message": "Account is already connected. Use force=true to reconnect.",
		})
		return
	}

	// Disconnect and reconnect
	client, ok := h.clientManager.GetClient(accountID)
	if ok {
		client.Disconnect()
	}

	// Start the client
	if err := h.clientManager.StartClient(accountID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to start client",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"account_id": accountID,
		"status": "qr_generating",
		"message": "Generando nuevo QR...",
	})
}

// PostLogout logs out and disconnects an account
func (h *Handlers) PostLogout(c *gin.Context) {
	accountID := c.Param("accountId")

	if err := h.clientManager.Logout(accountID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to logout",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Sesión cerrada correctamente",
	})
}

// SendMessageRequest represents the request body for sending a message
type SendMessageRequest struct {
	AccountID string `json:"account_id" binding:"required"`
	To        string `json:"to" binding:"required"`
	Message   string `json:"message" binding:"required"`
}

// PostSend sends a message
func (h *Handlers) PostSend(c *gin.Context) {
	var req SendMessageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
			"message": err.Error(),
		})
		return
	}

	// Check rate limit
	allowed, err := h.rateLimiter.Check(context.Background(), req.AccountID, req.To)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Rate limit check failed",
			"message": err.Error(),
		})
		return
	}

	if !allowed {
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error": "Rate limit exceeded",
			"message": "20 messages/hour limit reached for this destination",
			"code": "RATE_LIMIT_EXCEEDED",
			"retry_after": 3600,
		})
		return
	}

	// Send message
	if err := h.clientManager.SendTextMessage(req.AccountID, req.To, req.Message); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to send message",
			"message": err.Error(),
		})
		return
	}

	// Increment rate limit counters
	if err := h.rateLimiter.Increment(context.Background(), req.AccountID, req.To); err != nil {
		// Log error but don't fail the request
		// TODO: add proper logging
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message_id": "", // TODO: return actual message ID from whatsmeow
		"timestamp": time.Now().Format(time.RFC3339),
		"to_phone": req.To,
	})
}
