package webhook

import (
	"net/http"
	"time"
)

// WebhookPayload represents the payload sent to AI services
type WebhookPayload struct {
	Phone          string           `json:"phone"`
	FromNumber     string           `json:"from_number,omitempty"` // Full JID (user@server) - preserves original server type (lid, s.whatsapp.net, etc.)
	Content        string           `json:"content,omitempty"`
	Message        string           `json:"message"`
	MessageType    string           `json:"message_type,omitempty"`
	SelectedOption string           `json:"selected_option,omitempty"`
	FlowPayload    map[string]any   `json:"flow_payload,omitempty"`
	Location       *LocationPayload `json:"location,omitempty"`
	Timestamp      string           `json:"timestamp"`
	AccountID      string           `json:"account_id"` // "bot-clientes" or "bot-proveedores" - determines routing
	MediaBase64    string           `json:"media_base64,omitempty"`
	MediaMimetype  string           `json:"media_mimetype,omitempty"`
	MediaFilename  string           `json:"media_filename,omitempty"`
}

type LocationPayload struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	Name      string  `json:"name,omitempty"`
	Address   string  `json:"address,omitempty"`
}

type UIOption struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

type UIConfig struct {
	Type               string           `json:"type"`
	ID                 string           `json:"id,omitempty"`
	HeaderType         string           `json:"header_type,omitempty"`
	HeaderText         string           `json:"header_text,omitempty"`
	HeaderMediaURL     string           `json:"header_media_url,omitempty"`
	FooterText         string           `json:"footer_text,omitempty"`
	ListButtonText     string           `json:"list_button_text,omitempty"`
	ListSectionTitle   string           `json:"list_section_title,omitempty"`
	Options            []UIOption       `json:"options,omitempty"`
	TemplateName       string           `json:"template_name,omitempty"`
	TemplateLanguage   string           `json:"template_language,omitempty"`
	TemplateComponents []map[string]any `json:"template_components,omitempty"`
	FlowID             string           `json:"flow_id,omitempty"`
	FlowToken          string           `json:"flow_token,omitempty"`
	FlowCTA            string           `json:"flow_cta,omitempty"`
	FlowMode           string           `json:"flow_mode,omitempty"`
	FlowAction         string           `json:"flow_action,omitempty"`
	FlowActionPayload  map[string]any   `json:"flow_action_payload,omitempty"`
}

// WebhookResponse represents the response from AI services
type WebhookResponse struct {
	Success  bool              `json:"success"`
	Messages []ResponseMessage `json:"messages,omitempty"`
	UI       *UIConfig         `json:"ui,omitempty"`
	Error    string            `json:"error,omitempty"`
}

// ResponseMessage represents a response message
type ResponseMessage struct {
	Response     string    `json:"response"`
	MediaURL     string    `json:"media_url,omitempty"`
	MediaType    string    `json:"media_type,omitempty"`
	MediaCaption string    `json:"media_caption,omitempty"`
	UI           *UIConfig `json:"ui,omitempty"`
}

// WebhookClient manages HTTP webhooks to AI services
type WebhookClient struct {
	clientesURL    string // URL for ai-clientes
	proveedoresURL string // URL for ai-proveedores
	endpoint       string
	timeout        int
	retryAttempts  int
	httpClient     *http.Client
}

// NewWebhookClient creates a new webhook client with dynamic routing
func NewWebhookClient(clientesURL, proveedoresURL, endpoint string, timeoutMs, retryAttempts int) *WebhookClient {
	timeout := timeoutMs
	if timeout <= 0 {
		timeout = 10000
	}
	return &WebhookClient{
		clientesURL:    clientesURL,
		proveedoresURL: proveedoresURL,
		endpoint:       endpoint,
		timeout:        timeout,
		retryAttempts:  retryAttempts,
		httpClient: &http.Client{
			Timeout: time.Duration(timeout) * time.Millisecond,
		},
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
