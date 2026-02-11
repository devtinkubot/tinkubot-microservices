package webhook

// WebhookPayload represents the payload sent to AI services
type WebhookPayload struct {
	Phone         string `json:"phone"`
	FromNumber    string `json:"from_number,omitempty"` // Full JID (user@server) - preserves original server type (lid, s.whatsapp.net, etc.)
	Message       string `json:"message"`
	Timestamp     string `json:"timestamp"`
	AccountID     string `json:"account_id"` // "bot-clientes" or "bot-proveedores" - determines routing
	MediaBase64   string `json:"media_base64,omitempty"`
	MediaMimetype string `json:"media_mimetype,omitempty"`
	MediaFilename string `json:"media_filename,omitempty"`
}

// WebhookResponse represents the response from AI services
type WebhookResponse struct {
	Success  bool              `json:"success"`
	Messages []ResponseMessage `json:"messages,omitempty"`
	Error    string            `json:"error,omitempty"`
}

// ResponseMessage represents a response message
type ResponseMessage struct {
	Response     string `json:"response"`
	MediaURL     string `json:"media_url,omitempty"`
	MediaType    string `json:"media_type,omitempty"`
	MediaCaption string `json:"media_caption,omitempty"`
}

// WebhookClient manages HTTP webhooks to AI services
type WebhookClient struct {
	clientesURL    string // URL for ai-clientes
	proveedoresURL string // URL for ai-proveedores
	endpoint       string
	timeout        int
	retryAttempts  int
}

// NewWebhookClient creates a new webhook client with dynamic routing
func NewWebhookClient(clientesURL, proveedoresURL, endpoint string, timeoutMs, retryAttempts int) *WebhookClient {
	return &WebhookClient{
		clientesURL:    clientesURL,
		proveedoresURL: proveedoresURL,
		endpoint:       endpoint,
		timeout:        timeoutMs,
		retryAttempts:  retryAttempts,
	}
}

// getURL determines the URL based on the account_id
func (wc *WebhookClient) getURL(accountID string) string {
	if accountID == "bot-clientes" {
		return wc.clientesURL + wc.endpoint
	}
	if accountID == "bot-proveedores" {
		return wc.proveedoresURL + wc.endpoint
	}
	// Default: use providers
	return wc.proveedoresURL + wc.endpoint
}
