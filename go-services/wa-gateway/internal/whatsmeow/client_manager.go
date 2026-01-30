package whatsmeow

import (
	"context"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"google.golang.org/protobuf/proto"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// Event represents a WhatsApp event to be broadcasted via SSE
type Event struct {
	Type      string                 `json:"type"` // qr_ready, connected, disconnected, error
	AccountID string                 `json:"account_id"`
	Data      map[string]interface{} `json:"data"`
	Timestamp time.Time              `json:"timestamp"`
}

// ClientManager manages multiple whatsmeow clients
type ClientManager struct {
	clients       map[string]*whatsmeow.Client
	db            *pgxpool.Pool
	container     *sqlstore.Container
	eventHandlers []func(Event)
	mu            sync.RWMutex
}

// NewClientManager creates a new ClientManager
func NewClientManager(db *pgxpool.Pool, databaseURL string) (*ClientManager, error) {
	// Create logger for sqlstore
	log := waLog.Stdout("WA-Gateway", "INFO", true)

	// Create sqlstore container with pgx driver (latest API requires context and logger)
	container, err := sqlstore.New(context.Background(), "pgx", databaseURL, log)
	if err != nil {
		return nil, fmt.Errorf("failed to create sqlstore: %w", err)
	}

	cm := &ClientManager{
		clients:   make(map[string]*whatsmeow.Client),
		db:        db,
		container: container,
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

	if _, exists := cm.clients[accountID]; exists {
		return fmt.Errorf("client already exists for account: %s", accountID)
	}

	// Get the first device from the container (latest API requires context)
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

	// Update state to "connecting"
	if err := cm.updateConnectionStatus(accountID, "connecting", nil); err != nil {
		log.Printf("[%s] Failed to update connection status to connecting: %v", accountID, err)
	}

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
		cm.updateConnectionStatus(accountID, "error", map[string]interface{}{
			"last_error": err.Error(),
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

			// Update database with QR code
			qrExpiresAt := time.Now().Add(2 * time.Minute)
			if err := cm.updateConnectionStatus(accountID, "qr_ready", map[string]interface{}{
				"qr_code":      qrCode,
				"qr_expires_at": qrExpiresAt,
			}); err != nil {
				log.Printf("[%s] Failed to update QR code in database: %v", accountID, err)
			}

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

	// Get phone number from JID
	phone := client.Store.ID.ToNonAD().String()
	if len(phone) > 15 {
		phone = phone[:15] // Limit length
	}

	// Update database
	if err := cm.updateConnectionStatus(accountID, "connected", map[string]interface{}{
		"phone_number":  phone,
		"connected_at":  time.Now(),
		"qr_code":       nil,
		"qr_expires_at": nil,
		"last_error":    nil,
	}); err != nil {
		log.Printf("[%s] Failed to update connection status: %v", accountID, err)
	}

	// Broadcast connected event
	cm.broadcastEvent("connected", accountID, map[string]interface{}{
		"phone_number": phone,
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

	// Update database
	if err := cm.updateConnectionStatus(accountID, "disconnected", map[string]interface{}{
		"last_error": reason,
	}); err != nil {
		log.Printf("[%s] Failed to update disconnection status: %v", accountID, err)
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

// handleMessage handles incoming messages using the new API
func (cm *ClientManager) handleMessage(accountID string, msgEvt *events.Message) {
	// Ignore messages from broadcasts and groups
	// Check if it's a group using msg.Info.Chat.Server
	if msgEvt.Info.Chat.Server == "g.us" || msgEvt.Info.Chat.Server == "broadcast" {
		return
	}

	// Alternative check using ToNonAD()
	// chatJID := msgEvt.Info.Chat.ToNonAD()
	// if chatJID.Server == "g.us" || chatJID.Server == "broadcast" {
	//     return
	// }

	// Get account info to determine webhook URL
	ctx := context.Background()
	var webhookURL string
	err := cm.db.QueryRow(ctx, `
		SELECT webhook_url FROM wa_accounts WHERE account_id = $1
	`, accountID).Scan(&webhookURL)
	if err != nil {
		log.Printf("[%s] Failed to get webhook URL: %v", accountID, err)
		return
	}

	// Increment messages received counter
	if _, err := cm.db.Exec(ctx, `
		UPDATE wa_account_states
		SET messages_received = messages_received + 1
		WHERE account_id = $1
	`, accountID); err != nil {
		log.Printf("[%s] Failed to increment message counter: %v", accountID, err)
	}

	// Get message text using the new API
	messageText := msgEvt.Message.GetConversation()

	// TODO: Send webhook to AI service
	// For now, just log the message
	log.Printf("[%s] Message from %s: %s",
		accountID,
		msgEvt.Info.Chat.String(),
		messageText,
	)
}

// handleLoggedOut handles logout events
func (cm *ClientManager) handleLoggedOut(accountID string) {
	log.Printf("[%s] Logged out", accountID)

	if err := cm.updateConnectionStatus(accountID, "disconnected", map[string]interface{}{
		"last_error": "logged_out",
	}); err != nil {
		log.Printf("[%s] Failed to update status after logout: %v", accountID, err)
	}

	cm.broadcastEvent("disconnected", accountID, map[string]interface{}{
		"reason": "logged_out",
	})
}

// updateConnectionStatus updates the connection status in the database
func (cm *ClientManager) updateConnectionStatus(accountID, status string, extraData map[string]interface{}) error {
	ctx := context.Background()

	// Build dynamic UPDATE query
	query := `
		UPDATE wa_account_states
		SET connection_status = $1, updated_at = NOW()
	`
	args := []interface{}{status}
	argIdx := 2

	if status == "qr_ready" {
		if qrCode, ok := extraData["qr_code"].(string); ok {
			query += fmt.Sprintf(", qr_code = $%d", argIdx)
			args = append(args, qrCode)
			argIdx++
		}
		if expiresAt, ok := extraData["qr_expires_at"].(time.Time); ok {
			query += fmt.Sprintf(", qr_expires_at = $%d", argIdx)
			args = append(args, expiresAt)
			argIdx++
		}
	}

	if status == "connected" {
		if phoneNumber, ok := extraData["phone_number"].(string); ok {
			query += fmt.Sprintf(", phone_number = $%d", argIdx)
			args = append(args, phoneNumber)
			argIdx++
		}
		if connectedAt, ok := extraData["connected_at"].(time.Time); ok {
			query += fmt.Sprintf(", connected_at = $%d", argIdx)
			args = append(args, connectedAt)
			argIdx++
		}
		query += ", last_seen_at = NOW()"
		query += ", qr_code = NULL, qr_expires_at = NULL"
	}

	if status == "disconnected" || status == "error" {
		if lastError, ok := extraData["last_error"].(string); ok {
			query += fmt.Sprintf(", last_error = $%d", argIdx)
			args = append(args, lastError)
			argIdx++
		}
	}

	query += fmt.Sprintf(" WHERE account_id = $%d", argIdx)
	args = append(args, accountID)

	_, err := cm.db.Exec(ctx, query, args...)
	return err
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

	// Increment counter
	ctx := context.Background()
	if _, err := cm.db.Exec(ctx, `
		UPDATE wa_account_states
		SET messages_sent = messages_sent + 1
		WHERE account_id = $1
	`, accountID); err != nil {
		log.Printf("[%s] Failed to increment sent counter: %v", accountID, err)
	}

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
