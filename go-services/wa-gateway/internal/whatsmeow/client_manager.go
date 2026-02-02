package whatsmeow

import (
	"context"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/mdp/qrterminal/v3"
	_ "github.com/mattn/go-sqlite3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"google.golang.org/protobuf/proto"
	"github.com/tinkubot/wa-gateway/internal/webhook"
)

// Event represents a WhatsApp event to be broadcasted via SSE
type Event struct {
	Type      string                 `json:"type"` // qr_ready, connected, disconnected, error
	AccountID string                 `json:"account_id"`
	Data      map[string]interface{} `json:"data"`
	Timestamp time.Time              `json:"timestamp"`
}

// StoredQR stores a QR code with its expiration time
type StoredQR struct {
	QRCode     string
	ExpiresAt  time.Time
}

// ClientManager manages multiple whatsmeow clients
type ClientManager struct {
	clients       map[string]*whatsmeow.Client
	container     *sqlstore.Container
	eventHandlers []func(Event)
	qrCodes       map[string]*StoredQR // Store latest QR codes
	webhookClient *webhook.WebhookClient
	mu            sync.RWMutex
}

// NewClientManager creates a new ClientManager with SQLite
func NewClientManager(databasePath string, webhookClient *webhook.WebhookClient) (*ClientManager, error) {
	// Create logger for sqlstore
	log := waLog.Stdout("WA-Gateway", "INFO", true)

	// Create data directory if it doesn't exist
	if err := os.MkdirAll("data", 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	// Create sqlstore container with SQLite driver
	container, err := sqlstore.New(context.Background(), "sqlite3", databasePath, log)
	if err != nil {
		return nil, fmt.Errorf("failed to create sqlstore: %w", err)
	}

	cm := &ClientManager{
		clients:       make(map[string]*whatsmeow.Client),
		container:     container,
		qrCodes:       make(map[string]*StoredQR),
		webhookClient: webhookClient,
	}

	return cm, nil
}

// AddEventHandler adds a callback for WhatsApp events
func (cm *ClientManager) AddEventHandler(handler func(Event)) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.eventHandlers = append(cm.eventHandlers, handler)
}

// broadcastEvent sends an event to all registered handlers
func (cm *ClientManager) broadcastEvent(eventType string, accountID string, data map[string]interface{}) {
	event := Event{
		Type:      eventType,
		AccountID: accountID,
		Data:      data,
		Timestamp: time.Now(),
	}

	cm.mu.RLock()
	handlers := make([]func(Event), len(cm.eventHandlers))
	copy(handlers, cm.eventHandlers)
	cm.mu.RUnlock()

	for _, handler := range handlers {
		go func(h func(Event)) {
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[ClientManager] Panic in event handler: %v", r)
				}
			}()
			h(event)
		}(handler)
	}
}

// StartClient starts a WhatsApp client for the given account
func (cm *ClientManager) StartClient(accountID string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	// If client already exists, disconnect it first
	if client, exists := cm.clients[accountID]; exists {
		log.Printf("[%s] Client already exists, disconnecting first", accountID)
		client.Disconnect()
	}

	// Get the first device from the container (latest API requires context)
	// This will retrieve the previously saved session if it exists
	deviceStore, err := cm.container.GetFirstDevice(context.Background())
	if err != nil {
		return fmt.Errorf("failed to get device store: %w", err)
	}

	// Create whatsmeow client with device store and logger (use waLog logger)
	clientLog := waLog.Stdout(accountID, "INFO", true)
	client := whatsmeow.NewClient(deviceStore, clientLog)

	// Set up event handler
	client.AddEventHandler(cm.makeEventHandler(accountID))

	cm.clients[accountID] = client

	log.Printf("[%s] Client starting...", accountID)

	// IMPORTANT: Get QR channel BEFORE connecting (required by whatsmeow API)
	qrChan, err := client.GetQRChannel(context.Background())
	if err != nil {
		log.Printf("[%s] Failed to get QR channel: %v", accountID, err)
		// Continue anyway, QR might not be needed if already authenticated
	}

	// Start processing QR codes in background
	if qrChan != nil {
		go cm.processQRChannel(accountID, qrChan)
	}

	// Connect to WhatsApp
	if err := client.Connect(); err != nil {
		cm.broadcastEvent("error", accountID, map[string]interface{}{
			"error": err.Error(),
		})
		return fmt.Errorf("failed to connect client: %w", err)
	}

	log.Printf("[%s] Client started successfully", accountID)
	return nil
}

// makeEventHandler creates the event handler for a specific account
func (cm *ClientManager) makeEventHandler(accountID string) func(interface{}) {
	return func(evt interface{}) {
		switch v := evt.(type) {
		case *events.Connected:
			cm.handleConnected(accountID)
		case *events.Disconnected:
			cm.handleDisconnected(accountID, v)
		case *events.Message:
			cm.handleMessage(accountID, v)
		case *events.LoggedOut:
			cm.handleLoggedOut(accountID)
		default:
			// Log other event types for debugging
			log.Printf("[%s] Received event: %T", accountID, evt)
		}
	}
}

// processQRChannel processes QR codes from the channel in background
func (cm *ClientManager) processQRChannel(accountID string, qrChan <-chan whatsmeow.QRChannelItem) {
	log.Printf("[%s] Starting QR channel processor", accountID)

	for evt := range qrChan {
		if evt.Event == "code" {
			qrCode := evt.Code
			log.Printf("[%s] QR Code received: %s...", accountID, qrCode[:20])

			// Generate QR code terminal output
			qrterminal.GenerateHalfBlock(qrCode, qrterminal.L, os.Stdout)

			// QR expires in 2 minutes
			qrExpiresAt := time.Now().Add(2 * time.Minute)

			// Store QR code for retrieval via GET /accounts/:id/qr
			cm.mu.Lock()
			cm.qrCodes[accountID] = &StoredQR{
				QRCode:    qrCode,
				ExpiresAt: qrExpiresAt,
			}
			cm.mu.Unlock()

			// Broadcast QR event via SSE
			cm.broadcastEvent("qr_ready", accountID, map[string]interface{}{
				"qr_code":    qrCode,
				"expires_at": qrExpiresAt,
			})
		}
	}

	log.Printf("[%s] QR channel closed", accountID)
}

// handleConnected handles successful connection
func (cm *ClientManager) handleConnected(accountID string) {
	log.Printf("[%s] Connected successfully", accountID)

	client, ok := cm.GetClient(accountID)
	if !ok {
		log.Printf("[%s] Error: client not found in manager", accountID)
		return
	}

	// Clear QR code on successful connection
	cm.ClearQRCode(accountID)

	// Get phone number from JID
	phone := client.Store.ID.ToNonAD().String()
	if len(phone) > 15 {
		phone = phone[:15] // Limit length
	}

	// Broadcast connected event
	cm.broadcastEvent("connected", accountID, map[string]interface{}{
		"phone_number": phone,
		"connected_at": time.Now(),
	})
}

// handleDisconnected handles disconnection events using type assertion
func (cm *ClientManager) handleDisconnected(accountID string, discEvt interface{}) {
	log.Printf("[%s] Disconnected", accountID)

	// Extract disconnect reason using type assertion
	reason := "unknown"
	if discEvt != nil {
		// Type assertion to access the event
		if disconnected, ok := discEvt.(*events.Disconnected); ok {
			reason = fmt.Sprintf("reason: %v", disconnected)
		}
	}

	// Broadcast disconnected event
	cm.broadcastEvent("disconnected", accountID, map[string]interface{}{
		"reason": reason,
	})

	// Attempt auto-reconnect (always attempt unless explicitly logged out)
	log.Printf("[%s] Scheduling auto-reconnect in 5 seconds...", accountID)
	time.AfterFunc(5*time.Second, func() {
		if client, ok := cm.GetClient(accountID); ok {
			client.Connect()
		}
	})
}

// extractMessageText extracts text from a message, handling both simple and extended text messages
func extractMessageText(msg *waProto.Message) string {
	// Try simple conversation first
	if msg.Conversation != nil {
		return *msg.Conversation
	}

	// Try extended text message (quotes, links, etc.)
	if msg.ExtendedTextMessage != nil && msg.ExtendedTextMessage.Text != nil {
		return *msg.ExtendedTextMessage.Text
	}

	// For other message types, you could add more handlers here
	// (image captions, document descriptions, etc.)
	return ""
}

// handleMessage handles incoming messages using the new API
func (cm *ClientManager) handleMessage(accountID string, msgEvt *events.Message) {
	// Ignore messages from broadcasts and groups
	if msgEvt.Info.Chat.Server == "g.us" || msgEvt.Info.Chat.Server == "broadcast" {
		return
	}

	// Get message text using improved extraction
	messageText := extractMessageText(msgEvt.Message)

	// Extract phone number (remove @s.whatsapp.net suffix)
	phone := msgEvt.Info.Chat.String()
	if len(phone) > 15 {
		phone = phone[:15]
	}

	// Prepare webhook payload
	payload := &webhook.WebhookPayload{
		Phone:     phone,
		Message:   messageText,
		Timestamp: time.Now().Format(time.RFC3339),
		AccountID: accountID,
	}

	// Send webhook if configured
	if cm.webhookClient != nil {
		go func() {
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()

			resp, err := cm.webhookClient.Send(ctx, payload)
			if err != nil {
				log.Printf("[%s] Error sending webhook: %v", accountID, err)
				return
			}

			if !resp.Success {
				log.Printf("[%s] AI service returned error: %s", accountID, resp.Error)
				return
			}

			// Send response messages back to WhatsApp
			for _, msg := range resp.Messages {
				if err := cm.SendTextMessage(accountID, phone, msg.Response); err != nil {
					log.Printf("[%s] Error sending response: %v", accountID, err)
				}
			}
		}()
	} else {
		// Fallback: log only
		log.Printf("[%s] Message from %s: %s", accountID, phone, messageText)
	}
}

// handleLoggedOut handles logout events
func (cm *ClientManager) handleLoggedOut(accountID string) {
	log.Printf("[%s] Logged out", accountID)

	cm.broadcastEvent("disconnected", accountID, map[string]interface{}{
		"reason": "logged_out",
	})
}

// GetClient returns the client for the given account
func (cm *ClientManager) GetClient(accountID string) (*whatsmeow.Client, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	client, ok := cm.clients[accountID]
	return client, ok
}

// Logout logs out and disconnects the client
func (cm *ClientManager) Logout(accountID string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	// Clear QR code on logout
	delete(cm.qrCodes, accountID)

	client, ok := cm.clients[accountID]
	if !ok {
		return fmt.Errorf("client not found for account: %s", accountID)
	}

	if err := client.Logout(context.Background()); err != nil {
		log.Printf("[%s] Error during logout: %v", accountID, err)
	}

	// Disconnect() now returns nothing (no error)
	client.Disconnect()

	return nil
}

// SendTextMessage sends a text message to the specified JID using the new API
func (cm *ClientManager) SendTextMessage(accountID string, to string, message string) error {
	client, ok := cm.GetClient(accountID)
	if !ok {
		return fmt.Errorf("client not found for account: %s", accountID)
	}

	// Parse and send message
	jid, err := parseJID(to)
	if err != nil {
		return fmt.Errorf("invalid JID: %w", err)
	}

	// Send message using the new API with proto.String()
	msg := &waProto.Message{
		Conversation: proto.String(message),
	}

	// SendMessage now requires context as first parameter (latest API)
	_, err = client.SendMessage(context.Background(), jid, msg)
	if err != nil {
		return fmt.Errorf("failed to send message: %w", err)
	}

	log.Printf("[%s] Message sent to %s", accountID, to)

	return nil
}

// parseJID parses a phone number string into a JID
func parseJID(phone string) (types.JID, error) {
	if len(phone) == 0 {
		return types.JID{}, fmt.Errorf("empty phone number")
	}

	// Remove any non-digit characters
	cleaned := ""
	for _, r := range phone {
		if r >= '0' && r <= '9' {
			cleaned += string(r)
		}
	}

	if len(cleaned) == 0 {
		return types.JID{}, fmt.Errorf("invalid phone number")
	}

	return types.NewJID(cleaned, types.DefaultUserServer), nil
}

// GetQRCode retrieves the stored QR code for an account
func (cm *ClientManager) GetQRCode(accountID string) (string, *time.Time, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	storedQR, exists := cm.qrCodes[accountID]
	if !exists {
		return "", nil, false
	}

	// Check if QR has expired
	if time.Now().After(storedQR.ExpiresAt) {
		return "", nil, false
	}

	return storedQR.QRCode, &storedQR.ExpiresAt, true
}

// ClearQRCode removes the stored QR code for an account
func (cm *ClientManager) ClearQRCode(accountID string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	delete(cm.qrCodes, accountID)
}
