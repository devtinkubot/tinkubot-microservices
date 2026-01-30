package api

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/ratelimit"
	"github.com/tinkubot/wa-gateway/internal/whatsmeow"
)

// Handlers holds the dependencies for HTTP handlers
type Handlers struct {
	clientManager *whatsmeow.ClientManager
	rateLimiter   *ratelimit.Limiter
	sseHub        *SSEHub
}

// NewHandlers creates a new Handlers instance
func NewHandlers(cm *whatsmeow.ClientManager, rl *ratelimit.Limiter, sseHub *SSEHub) *Handlers {
	return &Handlers{
		clientManager: cm,
		rateLimiter:   rl,
		sseHub:        sseHub,
	}
}

// Account represents an account with its state
type Account struct {
	ID               string       `json:"id"`
	AccountID        string       `json:"account_id"`
	AccountType      string       `json:"account_type"`
	DisplayName      string       `json:"display_name"`
	ConnectionStatus string       `json:"connection_status"`
	QRCode           string       `json:"qr_code,omitempty"`
	QRExpiresAt      *time.Time   `json:"qr_expires_at,omitempty"`
	ConnectedAt      *time.Time   `json:"connected_at,omitempty"`
}

// GetHealth returns health check information
func (h *Handlers) GetHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":         "healthy",
		"service":        "wa-gateway",
		"version":        "1.0.0",
		"timestamp":      time.Now().Format(time.RFC3339),
		"dependencies": gin.H{
			"sqlite": gin.H{
				"status": "healthy",
			},
		},
	})
}

// GetAccounts returns all accounts with their connection status
func (h *Handlers) GetAccounts(c *gin.Context) {
	// Return known accounts
	accounts := []Account{
		{
			ID:               "bot-clientes",
			AccountID:        "bot-clientes",
			AccountType:      "clientes",
			DisplayName:      "Bot Clientes",
			ConnectionStatus: "disconnected",
		},
		{
			ID:               "bot-proveedores",
			AccountID:        "bot-proveedores",
			AccountType:      "proveedores",
			DisplayName:      "Bot Proveedores",
			ConnectionStatus: "disconnected",
		},
	}

	// Update connection status based on actual client state
	for i := range accounts {
		if client, ok := h.clientManager.GetClient(accounts[i].AccountID); ok {
			if client.IsLoggedIn() {
				accounts[i].ConnectionStatus = "connected"
				now := time.Now()
				accounts[i].ConnectedAt = &now
			} else if client.IsConnected() {
				accounts[i].ConnectionStatus = "qr_ready"
				// Include QR code if available
				if qrCode, expiresAt, exists := h.clientManager.GetQRCode(accounts[i].AccountID); exists {
					accounts[i].QRCode = qrCode
					accounts[i].QRExpiresAt = expiresAt
				}
			} else {
				accounts[i].ConnectionStatus = "disconnected"
			}
		}
	}

	c.JSON(http.StatusOK, accounts)
}

// GetAccount returns a single account by ID
func (h *Handlers) GetAccount(c *gin.Context) {
	accountID := c.Param("accountId")

	// Define known accounts
	knownAccounts := map[string]Account{
		"bot-clientes": {
			ID:          "bot-clientes",
			AccountID:   "bot-clientes",
			AccountType: "clientes",
			DisplayName: "Bot Clientes",
		},
		"bot-proveedores": {
			ID:          "bot-proveedores",
			AccountID:   "bot-proveedores",
			AccountType: "proveedores",
			DisplayName: "Bot Proveedores",
		},
	}

	acc, exists := knownAccounts[accountID]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error":    "Account not found",
			"message":  "No account found with ID " + accountID,
			"code":     "ACCOUNT_NOT_FOUND",
		})
		return
	}

	// Update connection status
	if client, ok := h.clientManager.GetClient(accountID); ok {
		if client.IsLoggedIn() {
			acc.ConnectionStatus = "connected"
			now := time.Now()
			acc.ConnectedAt = &now
		} else if client.IsConnected() {
			acc.ConnectionStatus = "qr_ready"
			// Include QR code if available
			if qrCode, expiresAt, exists := h.clientManager.GetQRCode(accountID); exists {
				acc.QRCode = qrCode
				acc.QRExpiresAt = expiresAt
			}
		} else {
			acc.ConnectionStatus = "disconnected"
		}
	} else {
		acc.ConnectionStatus = "disconnected"
	}

	c.JSON(http.StatusOK, acc)
}

// GetQR returns the QR code for an account
func (h *Handlers) GetQR(c *gin.Context) {
	accountID := c.Param("accountId")

	// Check if account exists
	if accountID != "bot-clientes" && accountID != "bot-proveedores" {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Account not found",
		})
		return
	}

	// Check if client is already connected
	if client, ok := h.clientManager.GetClient(accountID); ok && client.IsLoggedIn() {
		c.JSON(http.StatusNotFound, gin.H{
			"error":    "QR not available",
			"message":  "Account is already connected",
		})
		return
	}

	// Try to get stored QR code
	qrCode, expiresAt, exists := h.clientManager.GetQRCode(accountID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error":    "QR not available",
			"message":  "Use POST /login to generate QR code",
		})
		return
	}

	// Return QR code
	c.JSON(http.StatusOK, gin.H{
		"account_id":  accountID,
		"qr_code":     qrCode,
		"qr_expires_at": expiresAt,
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
	if accountID != "bot-clientes" && accountID != "bot-proveedores" {
		c.JSON(http.StatusNotFound, gin.H{
			"error":    "Account not found",
			"message":  "No account found with ID " + accountID,
		})
		return
	}

	// Check if already connected
	if client, ok := h.clientManager.GetClient(accountID); ok && client.IsLoggedIn() && !req.Force {
		c.JSON(http.StatusConflict, gin.H{
			"error":    "Already connected",
			"message":  "Account is already connected. Use force=true to reconnect.",
		})
		return
	}

	// Disconnect if force reconnect
	if req.Force {
		if client, ok := h.clientManager.GetClient(accountID); ok {
			client.Disconnect()
		}
		// Clear old QR code when forcing reconnect
		h.clientManager.ClearQRCode(accountID)
	}

	// Start the client (will generate QR)
	if err := h.clientManager.StartClient(accountID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":    "Failed to start client",
			"message":  err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":   true,
		"account_id": accountID,
		"status":    "qr_generating",
		"message":   "Generando nuevo QR...",
	})
}

// PostLogout logs out and disconnects an account
func (h *Handlers) PostLogout(c *gin.Context) {
	accountID := c.Param("accountId")

	if err := h.clientManager.Logout(accountID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":    "Failed to logout",
			"message":  err.Error(),
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
			"error":    "Invalid request",
			"message":  err.Error(),
		})
		return
	}

	// Check rate limit
	allowed, retryAfter, err := h.rateLimiter.Check(context.Background(), req.AccountID, req.To)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":    "Rate limit check failed",
			"message":  err.Error(),
		})
		return
	}

	if !allowed {
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error":       "Rate limit exceeded",
			"message":     err.Error(),
			"code":        "RATE_LIMIT_EXCEEDED",
			"retry_after": int(retryAfter.Seconds()),
		})
		return
	}

	// Send message
	if err := h.clientManager.SendTextMessage(req.AccountID, req.To, req.Message); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":    "Failed to send message",
			"message":  err.Error(),
		})
		return
	}

	// Increment rate limit counters
	if err := h.rateLimiter.Increment(context.Background(), req.AccountID, req.To); err != nil {
		// Log error but don't fail the request
		// TODO: add proper logging
	}

	c.JSON(http.StatusOK, gin.H{
		"success":   true,
		"message_id": "",
		"timestamp":  time.Now().Format(time.RFC3339),
		"to_phone":   req.To,
	})
}
