package api

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/metawebhook"
)

// GetMetaWebhook handles Meta webhook verification challenge.
func (h *Handlers) GetMetaWebhook(c *gin.Context) {
	if h.metaWebhook == nil || !h.metaWebhook.Enabled() {
		c.Status(http.StatusNotFound)
		return
	}

	statusCode, body := h.metaWebhook.VerifyChallenge(
		c.Query("hub.mode"),
		c.Query("hub.verify_token"),
		c.Query("hub.challenge"),
	)
	c.String(statusCode, body)
}

// PostMetaWebhook receives webhook events from Meta WhatsApp Cloud API.
func (h *Handlers) PostMetaWebhook(c *gin.Context) {
	if h.metaWebhook == nil || !h.metaWebhook.Enabled() {
		c.Status(http.StatusNotFound)
		return
	}

	body, err := c.GetRawData()
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "invalid request body",
		})
		return
	}

	signature := c.GetHeader("X-Hub-Signature-256")
	if err := h.metaWebhook.ProcessEvent(c.Request.Context(), signature, body); err != nil {
		switch {
		case errors.Is(err, metawebhook.ErrUnauthorized):
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid signature"})
			return
		case errors.Is(err, metawebhook.ErrForbidden):
			c.JSON(http.StatusForbidden, gin.H{"error": "event rejected"})
			return
		default:
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{"success": true})
}
