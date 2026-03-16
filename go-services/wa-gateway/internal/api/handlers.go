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
)

// Handlers holds the dependencies for HTTP handlers
type Handlers struct {
	rateLimiter   *ratelimit.Limiter
	eventRecorder ratelimit.EventRecorder
	metaWebhook   *metawebhook.Service
	outbound      *outbound.Router
}

type HandlerConfig struct {
	EventRecorder       ratelimit.EventRecorder
}

// NewHandlers creates a new Handlers instance
func NewHandlers(
	rl *ratelimit.Limiter,
	metaWebhook *metawebhook.Service,
	outboundRouter *outbound.Router,
	cfg HandlerConfig,
) *Handlers {
	return &Handlers{
		rateLimiter:   rl,
		eventRecorder: cfg.EventRecorder,
		metaWebhook:   metaWebhook,
		outbound:      outboundRouter,
	}
}

// GetHealth returns health check information
func (h *Handlers) GetHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"service":   "wa-gateway",
		"version":   "1.0.0",
		"timestamp": time.Now().Format(time.RFC3339),
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
