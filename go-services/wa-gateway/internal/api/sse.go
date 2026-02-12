package api

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/whatsmeow"
)

// SSEClient represents a connected SSE client
type SSEClient struct {
	ID      string
	Channel chan whatsmeow.Event
}

// SSEHub manages SSE client connections
type SSEHub struct {
	clients map[string]*SSEClient
	mu      sync.RWMutex
}

// NewSSEHub creates a new SSE hub
func NewSSEHub() *SSEHub {
	return &SSEHub{
		clients: make(map[string]*SSEClient),
	}
}

// AddClient adds a new SSE client
func (h *SSEHub) AddClient(client *SSEClient) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.clients[client.ID] = client
	log.Printf("[SSE] Client connected: %s (total: %d)", client.ID, len(h.clients))
}

// RemoveClient removes an SSE client
func (h *SSEHub) RemoveClient(clientID string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if client, ok := h.clients[clientID]; ok {
		close(client.Channel)
		delete(h.clients, clientID)
		log.Printf("[SSE] Client disconnected: %s (total: %d)", clientID, len(h.clients))
	}
}

// Broadcast sends an event to all connected clients
func (h *SSEHub) Broadcast(event whatsmeow.Event) {
	h.mu.RLock()
	deadClients := []string{}

	for clientID, client := range h.clients {
		select {
		case client.Channel <- event:
			// Event sent successfully
		default:
			// Channel is full or closed, mark for removal
			deadClients = append(deadClients, clientID)
		}
	}
	h.mu.RUnlock()

	// Remove dead clients
	for _, clientID := range deadClients {
		h.RemoveClient(clientID)
	}
}

// GetClientCount returns the number of connected clients
func (h *SSEHub) GetClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

// EventStream handles SSE connections for real-time updates
func (h *Handlers) EventStream(c *gin.Context) {
	// Set headers for SSE
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")

	// Get filter parameters (optional)
	accountsFilter := c.Query("accounts") // comma-separated list
	eventsFilter := c.Query("events")     // comma-separated list

	// Create client channel with buffer
	clientChan := make(chan whatsmeow.Event, 100)

	// Create SSE client
	client := &SSEClient{
		ID:      generateSessionID(),
		Channel: clientChan,
	}

	// Add to hub
	h.sseHub.AddClient(client)
	defer h.sseHub.RemoveClient(client.ID)

	// Send initial connection message
	sendSSEEvent(c.Writer, "connected", map[string]interface{}{
		"client_id": client.ID,
		"timestamp": time.Now().Format(time.RFC3339),
	})

	// Keep connection alive with heartbeat
	ctx := c.Request.Context()
	heartbeat := time.NewTicker(30 * time.Second)
	defer heartbeat.Stop()

	// Event loop
	for {
		select {
		case <-ctx.Done():
			// Client disconnected
			return

		case event := <-clientChan:
			// Apply filters if specified
			if accountsFilter != "" && !contains(accountsFilter, event.AccountID) {
				continue
			}
			if eventsFilter != "" && !contains(eventsFilter, event.Type) {
				continue
			}

			// Send event to client
			if !sendSSEEvent(c.Writer, event.Type, map[string]interface{}{
				"account_id": event.AccountID,
				"data":       event.Data,
				"timestamp":  event.Timestamp.Format(time.RFC3339),
			}) {
				// Failed to send, client likely disconnected
				return
			}

		case <-heartbeat.C:
			// Send heartbeat to keep connection alive
			if !sendSSEEvent(c.Writer, "heartbeat", map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			}) {
				return
			}
		}
	}
}

// sendSSEEvent sends a single SSE event
func sendSSEEvent(writer gin.ResponseWriter, eventType string, data map[string]interface{}) bool {
	// Format: event: <eventType>\ndata: <json>\n\n

	jsonData, err := json.Marshal(data)
	if err != nil {
		log.Printf("[SSE] Error marshaling event: %v", err)
		return false
	}

	// Write event
	if _, err := writer.Write([]byte("event: " + eventType + "\n")); err != nil {
		return false
	}

	// Write data
	if _, err := writer.Write([]byte("data: " + string(jsonData) + "\n\n")); err != nil {
		return false
	}

	// Flush to client
	if flusher, ok := writer.(http.Flusher); ok {
		flusher.Flush()
	}

	return true
}

// generateSessionID generates a random session ID
func generateSessionID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		log.Printf("[SSE] Error generating session ID: %v", err)
		return "unknown"
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// contains checks if a comma-separated string contains a value
func contains(list, value string) bool {
	for _, item := range splitComma(list) {
		if item == value {
			return true
		}
	}
	return false
}

// splitComma splits a comma-separated string
func splitComma(s string) []string {
	if s == "" {
		return []string{}
	}
	result := []string{}
	current := ""
	for _, r := range s {
		if r == ',' {
			if current != "" {
				result = append(result, current)
				current = ""
			}
		} else {
			current += string(r)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}
