package webhook

import (
	"log"
	"net/http"
	"strings"
	"time"
)

// WebhookPayload represents the payload sent to AI services
type WebhookPayload struct {
	Phone          string           `json:"phone"`
	FromNumber     string           `json:"from_number,omitempty"` // Full JID (user@server) - preserves original server type (lid, s.whatsapp.net, etc.)
	UserID         string           `json:"user_id,omitempty"`     // BSUID - Business-Scoped User ID
	DisplayName    string           `json:"display_name,omitempty"`
	FormattedName  string           `json:"formatted_name,omitempty"`
	FirstName      string           `json:"first_name,omitempty"`
	LastName       string           `json:"last_name,omitempty"`
	Username       string           `json:"username,omitempty"`
	CountryCode    string           `json:"country_code,omitempty"`
	ContextFrom    string           `json:"context_from,omitempty"`
	ContextID      string           `json:"context_id,omitempty"`
	Content        string           `json:"content,omitempty"`
	Message        string           `json:"message"`
	MessageType    string           `json:"message_type,omitempty"`
	SelectedOption string           `json:"selected_option,omitempty"`
	FlowPayload    map[string]any   `json:"flow_payload,omitempty"`
	Location       *LocationPayload `json:"location,omitempty"`
	Timestamp      string           `json:"timestamp"`
	MessageID      string           `json:"id,omitempty"`      // Meta message ID for idempotency
	AccountID      string           `json:"account_id"`        // "bot-clientes" or "bot-proveedores" - determines routing
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
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
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

type ContactName struct {
	FormattedName string `json:"formatted_name"`
	FirstName     string `json:"first_name,omitempty"`
	LastName      string `json:"last_name,omitempty"`
}

type ContactPhone struct {
	Phone string `json:"phone"`
	Type  string `json:"type,omitempty"`
	WAID  string `json:"wa_id,omitempty"`
}

type Contact struct {
	Name   ContactName    `json:"name"`
	Phones []ContactPhone `json:"phones,omitempty"`
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
	Contacts     []Contact `json:"contacts,omitempty"`
	UI           *UIConfig `json:"ui,omitempty"`
}

// WebhookClient manages HTTP webhooks to AI services
type WebhookClient struct {
	clientesURL       string // URL for ai-clientes
	proveedoresURL    string // URL for ai-proveedores
	onboardingRustURL string // URL for Rust onboarding
	rustTestNumbers   map[string]bool
	internalToken     string
	endpoint          string
	timeout           int
	retryAttempts     int
	httpClient        *http.Client
}

// NewWebhookClient creates a new webhook client with dynamic routing
func NewWebhookClient(
	clientesURL,
	proveedoresURL,
	onboardingRustURL,
	rustTestNumbersRaw,
	internalToken,
	endpoint string,
	timeoutMs,
	retryAttempts int,
) *WebhookClient {
	timeout := timeoutMs
	if timeout <= 0 {
		timeout = 10000
	}
	rustTestNumbers := make(map[string]bool)
	for _, num := range strings.Split(rustTestNumbersRaw, ",") {
		if normalized := normalizePhoneNumber(num); normalized != "" {
			rustTestNumbers[normalized] = true
		}
	}
	return &WebhookClient{
		clientesURL:       clientesURL,
		proveedoresURL:    proveedoresURL,
		onboardingRustURL: onboardingRustURL,
		rustTestNumbers:   rustTestNumbers,
		internalToken:     strings.TrimSpace(internalToken),
		endpoint:          endpoint,
		timeout:           timeout,
		retryAttempts:     retryAttempts,
		httpClient: &http.Client{
			Timeout: time.Duration(timeout) * time.Millisecond,
		},
	}
}

// isRustTestNumber checks whether the given phone is configured for Rust onboarding.
func (wc *WebhookClient) isRustTestNumber(fromNumber string) bool {
	normalized := normalizePhoneNumber(fromNumber)
	if normalized == "" {
		return false
	}
	return wc.rustTestNumbers[normalized]
}

// getURL determines the URL based on the account_id and onboarding routing rules.
func (wc *WebhookClient) getURL(payload *WebhookPayload) string {
	if payload.AccountID == "bot-proveedores" && wc.isRustTestNumber(payload.FromNumber) {
		if wc.onboardingRustURL != "" {
			log.Printf("[Webhook] Routing to Rust onboarding: from=%s account=%s", payload.FromNumber, payload.AccountID)
			return wc.onboardingRustURL + wc.endpoint
		}
		log.Printf("[Webhook] WARNING: Rust URL not configured, falling back to Python: from=%s", payload.FromNumber)
	}

	if payload.AccountID == "bot-clientes" {
		return wc.clientesURL + wc.endpoint
	}
	if payload.AccountID == "bot-proveedores" {
		return wc.proveedoresURL + wc.endpoint
	}
	// Default: use providers
	return wc.proveedoresURL + wc.endpoint
}

func normalizePhoneNumber(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return ""
	}

	if idx := strings.Index(value, "@"); idx > 0 {
		value = value[:idx]
	}

	var digits strings.Builder
	for _, ch := range value {
		if ch >= '0' && ch <= '9' {
			digits.WriteRune(ch)
		}
	}
	if digits.Len() == 0 {
		return ""
	}

	return "+" + digits.String()
}
