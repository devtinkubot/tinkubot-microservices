package api

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/metawebhook"
	"github.com/tinkubot/wa-gateway/internal/outbound"
	"github.com/tinkubot/wa-gateway/internal/ratelimit"
	"github.com/tinkubot/wa-gateway/internal/webhook"
	"github.com/tinkubot/wa-gateway/internal/whatsmeow"
)

// Handlers holds the dependencies for HTTP handlers
type Handlers struct {
	clientManager *whatsmeow.ClientManager
	rateLimiter   *ratelimit.Limiter
	eventRecorder ratelimit.EventRecorder
	sseHub        *SSEHub
	metaWebhook   *metawebhook.Service
	outbound      *outbound.Router
	metaManaged   map[string]bool
}

type HandlerConfig struct {
	MetaManagedAccounts map[string]bool
	EventRecorder       ratelimit.EventRecorder
}

// NewHandlers creates a new Handlers instance
func NewHandlers(
	cm *whatsmeow.ClientManager,
	rl *ratelimit.Limiter,
	sseHub *SSEHub,
	metaWebhook *metawebhook.Service,
	outboundRouter *outbound.Router,
	cfg HandlerConfig,
) *Handlers {
	metaManaged := cfg.MetaManagedAccounts
	if metaManaged == nil {
		metaManaged = map[string]bool{}
	}
	return &Handlers{
		clientManager: cm,
		rateLimiter:   rl,
		eventRecorder: cfg.EventRecorder,
		sseHub:        sseHub,
		metaWebhook:   metaWebhook,
		outbound:      outboundRouter,
		metaManaged:   metaManaged,
	}
}

// Account represents an account with its state
type Account struct {
	ID               string     `json:"id"`
	AccountID        string     `json:"account_id"`
	AccountType      string     `json:"account_type"`
	DisplayName      string     `json:"display_name"`
	ConnectionStatus string     `json:"connection_status"`
	Transport        string     `json:"transport,omitempty"`
	QRCode           string     `json:"qr_code,omitempty"`
	QRExpiresAt      *time.Time `json:"qr_expires_at,omitempty"`
	ConnectedAt      *time.Time `json:"connected_at,omitempty"`
}

var knownAccounts = map[string]Account{
	"bot-clientes": {
		ID:          "bot-clientes",
		AccountID:   "bot-clientes",
		AccountType: "clientes",
		DisplayName: "Bot Clientes",
		Transport:   "whatsmeow",
	},
	"bot-proveedores": {
		ID:          "bot-proveedores",
		AccountID:   "bot-proveedores",
		AccountType: "proveedores",
		DisplayName: "Bot Proveedores",
		Transport:   "whatsmeow",
	},
}

func (h *Handlers) isMetaManaged(accountID string) bool {
	if h == nil {
		return false
	}
	return h.metaManaged[accountID]
}

func (h *Handlers) buildAccount(accountID string) Account {
	acc := knownAccounts[accountID]
	if h.isMetaManaged(accountID) {
		acc.ConnectionStatus = "meta_managed"
		acc.Transport = "meta"
		return acc
	}

	acc.ConnectionStatus = "disconnected"
	acc.Transport = "whatsmeow"
	if h.clientManager == nil {
		return acc
	}

	client, ok := h.clientManager.GetClient(accountID)
	if !ok {
		return acc
	}
	if client.IsLoggedIn() {
		acc.ConnectionStatus = "connected"
		now := time.Now()
		acc.ConnectedAt = &now
		return acc
	}
	if client.IsConnected() {
		acc.ConnectionStatus = "qr_ready"
		if qrCode, expiresAt, exists := h.clientManager.GetQRCode(accountID); exists {
			acc.QRCode = qrCode
			acc.QRExpiresAt = expiresAt
		}
	}
	return acc
}

func (h *Handlers) metaOperationNotApplicable(c *gin.Context, accountID string) bool {
	if !h.isMetaManaged(accountID) {
		return false
	}
	c.JSON(http.StatusConflict, gin.H{
		"error":      "Operation not applicable",
		"message":    "Account is managed by Meta Cloud API",
		"code":       "ACCOUNT_MANAGED_BY_META",
		"account_id": accountID,
	})
	return true
}

// GetHealth returns health check information
func (h *Handlers) GetHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"service":   "wa-gateway",
		"version":   "1.0.0",
		"timestamp": time.Now().Format(time.RFC3339),
		"dependencies": gin.H{
			"sqlite": gin.H{
				"status": "healthy",
			},
		},
	})
}

// GetAccounts returns all accounts with their connection status
func (h *Handlers) GetAccounts(c *gin.Context) {
	accountIDs := []string{"bot-clientes", "bot-proveedores"}
	accounts := make([]Account, 0, len(accountIDs))
	for _, accountID := range accountIDs {
		accounts = append(accounts, h.buildAccount(accountID))
	}

	c.JSON(http.StatusOK, accounts)
}

// GetAccount returns a single account by ID
func (h *Handlers) GetAccount(c *gin.Context) {
	accountID := c.Param("accountId")

	acc, exists := knownAccounts[accountID]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error":   "Account not found",
			"message": "No account found with ID " + accountID,
			"code":    "ACCOUNT_NOT_FOUND",
		})
		return
	}

	_ = acc
	c.JSON(http.StatusOK, h.buildAccount(accountID))
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
	if h.metaOperationNotApplicable(c, accountID) {
		return
	}

	// Check if client is already connected
	if client, ok := h.clientManager.GetClient(accountID); ok && client.IsLoggedIn() {
		c.JSON(http.StatusNotFound, gin.H{
			"error":   "QR not available",
			"message": "Account is already connected",
		})
		return
	}

	// Try to get stored QR code
	qrCode, expiresAt, exists := h.clientManager.GetQRCode(accountID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error":   "QR not available",
			"message": "Use POST /login to generate QR code",
		})
		return
	}

	// Return QR code
	c.JSON(http.StatusOK, gin.H{
		"account_id":    accountID,
		"qr_code":       qrCode,
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
			"error":   "Account not found",
			"message": "No account found with ID " + accountID,
		})
		return
	}
	if h.metaOperationNotApplicable(c, accountID) {
		return
	}

	// Check if already connected
	if client, ok := h.clientManager.GetClient(accountID); ok && client.IsLoggedIn() && !req.Force {
		c.JSON(http.StatusConflict, gin.H{
			"error":   "Already connected",
			"message": "Account is already connected. Use force=true to reconnect.",
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
			"error":   "Failed to start client",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":    true,
		"account_id": accountID,
		"status":     "qr_generating",
		"message":    "Generando nuevo QR...",
	})
}

// PostLogout logs out and disconnects an account
func (h *Handlers) PostLogout(c *gin.Context) {
	accountID := c.Param("accountId")
	if h.metaOperationNotApplicable(c, accountID) {
		return
	}

	if err := h.clientManager.Logout(accountID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to logout",
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
	AccountID string            `json:"account_id" binding:"required"`
	To        string            `json:"to" binding:"required"`
	Message   string            `json:"message" binding:"required"`
	UI        *webhook.UIConfig `json:"ui,omitempty"`
	Metadata  *SendMetadata     `json:"metadata,omitempty"`
}

// SendMetadata identifies the source flow of an outbound send.
type SendMetadata struct {
	SourceService string `json:"source_service,omitempty"`
	FlowType      string `json:"flow_type,omitempty"`
	TaskType      string `json:"task_type,omitempty"`
	EventType     string `json:"event_type,omitempty"`
	TraceID       string `json:"trace_id,omitempty"`
	LeadEventID   string `json:"lead_event_id,omitempty"`
}

// PostSend sends a message
func (h *Handlers) PostSend(c *gin.Context) {
	var req SendMessageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request",
			"message": err.Error(),
		})
		return
	}

	log.Printf(
		"[PostSend] account=%s to=%s ui_type=%s metadata=%s",
		req.AccountID,
		req.To,
		uiTypeForLog(req.UI),
		metadataForLog(req.Metadata),
	)

	// Check rate limit
	allowed, retryAfter, decision, err := h.rateLimiter.Check(
		context.Background(),
		req.AccountID,
		req.To,
	)
	if err != nil {
		// El limiter retorna error descriptivo cuando el límite fue alcanzado.
		// Eso no es error interno: exponer 429 para que clientes puedan reintentar.
		if !allowed {
			h.recordRateLimitHit(c.Request.Context(), req, decision)
			retryAt := decision.RetryAt.Format(time.RFC3339)
			log.Printf(
				"[PostSend] rate_limited account=%s to=%s window=%s hour=%d/%d day=%d/%d retry_at=%s metadata=%s",
				req.AccountID,
				req.To,
				decision.Window,
				decision.MessagesLastHour,
				decision.LimitPerHour,
				decision.MessagesLast24H,
				decision.LimitPer24H,
				retryAt,
				metadataForLog(req.Metadata),
			)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":              "Rate limit exceeded",
				"message":            err.Error(),
				"code":               "RATE_LIMIT_EXCEEDED",
				"retry_after":        int(retryAfter.Seconds()),
				"retry_at":           retryAt,
				"account_id":         req.AccountID,
				"destination":        req.To,
				"window":             decision.Window,
				"messages_last_hour": decision.MessagesLastHour,
				"messages_last_24h":  decision.MessagesLast24H,
				"limit_per_hour":     decision.LimitPerHour,
				"limit_per_24h":      decision.LimitPer24H,
			})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Rate limit check failed",
			"message": err.Error(),
		})
		return
	}

	if !allowed {
		h.recordRateLimitHit(c.Request.Context(), req, decision)
		retryAt := decision.RetryAt.Format(time.RFC3339)
		log.Printf(
			"[PostSend] rate_limited account=%s to=%s window=%s hour=%d/%d day=%d/%d retry_at=%s metadata=%s",
			req.AccountID,
			req.To,
			decision.Window,
			decision.MessagesLastHour,
			decision.LimitPerHour,
			decision.MessagesLast24H,
			decision.LimitPer24H,
			retryAt,
			metadataForLog(req.Metadata),
		)
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error":              "Rate limit exceeded",
			"message":            "rate limit exceeded",
			"code":               "RATE_LIMIT_EXCEEDED",
			"retry_after":        int(retryAfter.Seconds()),
			"retry_at":           retryAt,
			"account_id":         req.AccountID,
			"destination":        req.To,
			"window":             decision.Window,
			"messages_last_hour": decision.MessagesLastHour,
			"messages_last_24h":  decision.MessagesLast24H,
			"limit_per_hour":     decision.LimitPerHour,
			"limit_per_24h":      decision.LimitPer24H,
		})
		return
	}

	// Send message through configured outbound transport.
	var sendErr error
	if req.UI == nil {
		sendErr = h.outbound.SendText(context.Background(), req.AccountID, req.To, req.Message)
	} else {
		switch req.UI.Type {
		case "buttons":
			sendErr = h.outbound.SendButtons(context.Background(), req.AccountID, req.To, req.Message, *req.UI)
		case "list":
			sendErr = h.outbound.SendList(context.Background(), req.AccountID, req.To, req.Message, *req.UI)
		case "location_request":
			sendErr = h.outbound.SendLocationRequest(context.Background(), req.AccountID, req.To, req.Message)
		case "flow":
			sendErr = h.outbound.SendFlow(context.Background(), req.AccountID, req.To, req.Message, *req.UI)
		case "template":
			sendErr = h.outbound.SendTemplate(context.Background(), req.AccountID, req.To, req.Message, *req.UI)
		default:
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "Invalid request",
				"message": "unsupported ui.type",
			})
			return
		}
	}
	if sendErr != nil {
		status := http.StatusInternalServerError
		if errors.Is(sendErr, outbound.ErrMetaNotConfigured) {
			status = http.StatusServiceUnavailable
		}
		log.Printf(
			"[PostSend] send_failed account=%s to=%s ui_type=%s metadata=%s err=%v",
			req.AccountID,
			req.To,
			uiTypeForLog(req.UI),
			metadataForLog(req.Metadata),
			sendErr,
		)
		c.JSON(status, gin.H{
			"error":   "Failed to send message",
			"message": sendErr.Error(),
		})
		return
	}

	// Increment rate limit counters
	if err := h.rateLimiter.Increment(context.Background(), req.AccountID, req.To); err != nil {
		// Log error but don't fail the request
		// TODO: add proper logging
	}
	log.Printf(
		"[PostSend] send_ok account=%s to=%s ui_type=%s metadata=%s",
		req.AccountID,
		req.To,
		uiTypeForLog(req.UI),
		metadataForLog(req.Metadata),
	)

	c.JSON(http.StatusOK, gin.H{
		"success":    true,
		"message_id": "",
		"timestamp":  time.Now().Format(time.RFC3339),
		"to_phone":   req.To,
	})
}

func (h *Handlers) recordRateLimitHit(
	ctx context.Context,
	req SendMessageRequest,
	decision ratelimit.Decision,
) {
	if h == nil || h.eventRecorder == nil {
		return
	}
	if err := h.eventRecorder.Record(ctx, ratelimit.Event{
		AccountID:        req.AccountID,
		Destination:      req.To,
		Window:           decision.Window,
		MessagesLastHour: decision.MessagesLastHour,
		MessagesLast24H:  decision.MessagesLast24H,
		LimitPerHour:     decision.LimitPerHour,
		LimitPer24H:      decision.LimitPer24H,
		RetryAt:          decision.RetryAt.Format(time.RFC3339),
		MetadataJSON:     metadataJSON(req.Metadata),
	}); err != nil {
		log.Printf("[PostSend] rate_limit_event_record_failed account=%s to=%s err=%v", req.AccountID, req.To, err)
	}
}

func metadataJSON(metadata *SendMetadata) string {
	if metadata == nil {
		return ""
	}
	raw, err := json.Marshal(metadata)
	if err != nil {
		return ""
	}
	return string(raw)
}

func metadataForLog(metadata *SendMetadata) string {
	if raw := metadataJSON(metadata); raw != "" {
		return raw
	}
	return "{}"
}

func uiTypeForLog(ui *webhook.UIConfig) string {
	if ui == nil {
		return "text"
	}
	return ui.Type
}
