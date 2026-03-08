package metaoutbound

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime"
	"net/http"
	"strings"
	"time"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

type Config struct {
	BaseURL       string
	APIVersion    string
	AccessToken   string
	AccessTokens  map[string]string
	Timeout       time.Duration
	RetryAttempts int
}

type Client struct {
	baseURL       string
	apiVersion    string
	accessToken   string
	accessTokens  map[string]string
	retryAttempts int
	httpClient    *http.Client
}

func NewClient(cfg Config) *Client {
	baseURL := strings.TrimSpace(cfg.BaseURL)
	if baseURL == "" {
		baseURL = "https://graph.facebook.com"
	}
	apiVersion := strings.TrimSpace(cfg.APIVersion)
	if apiVersion == "" {
		apiVersion = "v25.0"
	}
	timeout := cfg.Timeout
	if timeout <= 0 {
		timeout = 15 * time.Second
	}
	retryAttempts := cfg.RetryAttempts
	if retryAttempts < 0 {
		retryAttempts = 0
	}

	return &Client{
		baseURL:       strings.TrimRight(baseURL, "/"),
		apiVersion:    apiVersion,
		accessToken:   strings.TrimSpace(cfg.AccessToken),
		accessTokens:  normalizeAccessTokens(cfg.AccessTokens),
		retryAttempts: retryAttempts,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

func normalizeAccessTokens(raw map[string]string) map[string]string {
	if len(raw) == 0 {
		return map[string]string{}
	}

	normalized := make(map[string]string, len(raw))
	for phoneNumberID, token := range raw {
		phoneNumberID = strings.TrimSpace(phoneNumberID)
		token = strings.TrimSpace(token)
		if phoneNumberID == "" || token == "" {
			continue
		}
		normalized[phoneNumberID] = token
	}
	return normalized
}

func (c *Client) accessTokenFor(phoneNumberID string) string {
	if c == nil {
		return ""
	}
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	if token := strings.TrimSpace(c.accessTokens[phoneNumberID]); token != "" {
		return token
	}
	return strings.TrimSpace(c.accessToken)
}

type sendMessagePayload struct {
	MessagingProduct string              `json:"messaging_product"`
	RecipientType    string              `json:"recipient_type,omitempty"`
	To               string              `json:"to"`
	Type             string              `json:"type"`
	Text             *textPayload        `json:"text,omitempty"`
	Image            *imagePayload       `json:"image,omitempty"`
	Template         *templatePayload    `json:"template,omitempty"`
	Interactive      *interactivePayload `json:"interactive,omitempty"`
}

type textPayload struct {
	PreviewURL bool   `json:"preview_url"`
	Body       string `json:"body"`
}

type imagePayload struct {
	Link    string `json:"link"`
	Caption string `json:"caption,omitempty"`
}

type interactivePayload struct {
	Type   string             `json:"type"`
	Header *interactiveHeader `json:"header,omitempty"`
	Footer *interactiveFooter `json:"footer,omitempty"`
	Body   interactiveBody    `json:"body"`
	Action interactiveAction  `json:"action"`
}

type interactiveBody struct {
	Text string `json:"text"`
}

type interactiveHeader struct {
	Type  string                  `json:"type"`
	Text  string                  `json:"text,omitempty"`
	Image *interactiveHeaderMedia `json:"image,omitempty"`
}

type interactiveHeaderMedia struct {
	Link string `json:"link"`
}

type interactiveFooter struct {
	Text string `json:"text"`
}

const maxInteractiveFooterLen = 60

func normalizeFooterText(raw string) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return ""
	}
	runes := []rune(trimmed)
	if len(runes) <= maxInteractiveFooterLen {
		return trimmed
	}
	return string(runes[:maxInteractiveFooterLen])
}

type interactiveAction struct {
	Buttons    []interactiveButton  `json:"buttons,omitempty"`
	Button     string               `json:"button,omitempty"`
	Sections   []interactiveSection `json:"sections,omitempty"`
	Name       string               `json:"name,omitempty"`
	Parameters *interactiveFlowData `json:"parameters,omitempty"`
}

type interactiveSection struct {
	Title string           `json:"title,omitempty"`
	Rows  []interactiveRow `json:"rows,omitempty"`
}

type interactiveRow struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
}

type interactiveButton struct {
	Type  string                 `json:"type"`
	Reply interactiveButtonReply `json:"reply"`
}

type interactiveButtonReply struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

type interactiveFlowData struct {
	FlowMessageVersion string         `json:"flow_message_version,omitempty"`
	FlowID             string         `json:"flow_id,omitempty"`
	FlowToken          string         `json:"flow_token,omitempty"`
	FlowCTA            string         `json:"flow_cta,omitempty"`
	Mode               string         `json:"mode,omitempty"`
	FlowAction         string         `json:"flow_action,omitempty"`
	FlowActionPayload  map[string]any `json:"flow_action_payload,omitempty"`
}

type templatePayload struct {
	Name       string              `json:"name"`
	Language   templateLanguage    `json:"language"`
	Components []templateComponent `json:"components,omitempty"`
}

type templateLanguage struct {
	Code string `json:"code"`
}

type templateComponent struct {
	Type       string           `json:"type"`
	SubType    string           `json:"sub_type,omitempty"`
	Index      string           `json:"index,omitempty"`
	Parameters []map[string]any `json:"parameters,omitempty"`
}

type mediaMetadataResponse struct {
	URL      string `json:"url"`
	MimeType string `json:"mime_type,omitempty"`
	ID       string `json:"id,omitempty"`
}

// SendText sends a plain text WhatsApp message using Meta Cloud API.
func (c *Client) SendText(ctx context.Context, phoneNumberID, to, body string) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		return fmt.Errorf("message body is empty")
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "text",
		Text: &textPayload{
			PreviewURL: false,
			Body:       body,
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendImage sends an image message using Meta Cloud API.
func (c *Client) SendImage(ctx context.Context, phoneNumberID, to, imageURL, caption string) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	imageURL = strings.TrimSpace(imageURL)
	caption = strings.TrimSpace(caption)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if imageURL == "" {
		return fmt.Errorf("image url is empty")
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "image",
		Image: &imagePayload{
			Link:    imageURL,
			Caption: caption,
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendButtons sends an interactive button message using Meta Cloud API.
func (c *Client) SendButtons(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		return fmt.Errorf("message body is empty")
	}
	if len(ui.Options) == 0 {
		return fmt.Errorf("buttons options are empty")
	}

	buttons := make([]interactiveButton, 0, 3)
	for _, opt := range ui.Options {
		id := strings.TrimSpace(opt.ID)
		title := strings.TrimSpace(opt.Title)
		if id == "" || title == "" {
			continue
		}
		buttons = append(buttons, interactiveButton{
			Type: "reply",
			Reply: interactiveButtonReply{
				ID:    id,
				Title: title,
			},
		})
		if len(buttons) == 3 {
			break
		}
	}
	if len(buttons) == 0 {
		return fmt.Errorf("buttons options are invalid")
	}

	var header *interactiveHeader
	headerType := strings.ToLower(strings.TrimSpace(ui.HeaderType))
	switch headerType {
	case "":
	case "image":
		link := strings.TrimSpace(ui.HeaderMediaURL)
		if link == "" {
			return fmt.Errorf("buttons image header configured without header_media_url")
		}
		header = &interactiveHeader{
			Type:  "image",
			Image: &interactiveHeaderMedia{Link: link},
		}
	case "text":
		text := strings.TrimSpace(ui.HeaderText)
		if text == "" {
			return fmt.Errorf("buttons text header configured without header_text")
		}
		header = &interactiveHeader{
			Type: "text",
			Text: text,
		}
	default:
		return fmt.Errorf("unsupported buttons header_type: %s", headerType)
	}

	var footer *interactiveFooter
	footerText := normalizeFooterText(ui.FooterText)
	if original := strings.TrimSpace(ui.FooterText); original != "" && footerText != original {
		log.Printf("[MetaOutbound] buttons footer truncated original_len=%d truncated_len=%d", len([]rune(original)), len([]rune(footerText)))
	}
	if footerText != "" {
		footer = &interactiveFooter{Text: footerText}
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "interactive",
		Interactive: &interactivePayload{
			Type:   "button",
			Header: header,
			Footer: footer,
			Body:   interactiveBody{Text: body},
			Action: interactiveAction{
				Buttons: buttons,
			},
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendList sends an interactive list message using Meta Cloud API.
func (c *Client) SendList(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		return fmt.Errorf("message body is empty")
	}
	if len(ui.Options) == 0 {
		return fmt.Errorf("list options are empty")
	}

	rows := make([]interactiveRow, 0, 10)
	for _, opt := range ui.Options {
		id := strings.TrimSpace(opt.ID)
		title := strings.TrimSpace(opt.Title)
		description := strings.TrimSpace(opt.Description)
		if id == "" || title == "" {
			continue
		}
		rows = append(rows, interactiveRow{
			ID:          id,
			Title:       title,
			Description: description,
		})
		if len(rows) == 10 {
			break
		}
	}
	if len(rows) == 0 {
		return fmt.Errorf("list options are invalid")
	}

	buttonText := strings.TrimSpace(ui.ListButtonText)
	if buttonText == "" {
		buttonText = "Ver opciones"
	}
	sectionTitle := strings.TrimSpace(ui.ListSectionTitle)
	if sectionTitle == "" {
		sectionTitle = "Servicios"
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "interactive",
		Interactive: &interactivePayload{
			Type: "list",
			Body: interactiveBody{Text: body},
			Action: interactiveAction{
				Button:   buttonText,
				Sections: []interactiveSection{{Title: sectionTitle, Rows: rows}},
			},
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendLocationRequest sends a location request interactive message.
func (c *Client) SendLocationRequest(ctx context.Context, phoneNumberID, to, body string) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		return fmt.Errorf("message body is empty")
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "interactive",
		Interactive: &interactivePayload{
			Type: "location_request_message",
			Body: interactiveBody{Text: body},
			Action: interactiveAction{
				Name: "send_location",
			},
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendFlow sends a WhatsApp Flow interactive message.
func (c *Client) SendFlow(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		body = "Completa el formulario para continuar."
	}

	flowID := strings.TrimSpace(ui.FlowID)
	if flowID == "" {
		flowID = strings.TrimSpace(ui.ID)
	}
	if flowID == "" {
		return fmt.Errorf("flow_id is empty")
	}

	flowCTA := strings.TrimSpace(ui.FlowCTA)
	if flowCTA == "" {
		flowCTA = "Continuar"
	}

	mode := strings.TrimSpace(ui.FlowMode)
	if mode == "" {
		mode = "published"
	}

	flowAction := strings.TrimSpace(ui.FlowAction)
	if flowAction == "" {
		flowAction = "navigate"
	}

	parameters := &interactiveFlowData{
		FlowMessageVersion: "3",
		FlowID:             flowID,
		FlowToken:          strings.TrimSpace(ui.FlowToken),
		FlowCTA:            flowCTA,
		Mode:               mode,
		FlowAction:         flowAction,
		FlowActionPayload:  ui.FlowActionPayload,
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "interactive",
		Interactive: &interactivePayload{
			Type: "flow",
			Body: interactiveBody{Text: body},
			Action: interactiveAction{
				Name:       "flow",
				Parameters: parameters,
			},
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// SendTemplate sends a WhatsApp template message.
func (c *Client) SendTemplate(
	ctx context.Context,
	phoneNumberID, to string,
	ui webhook.UIConfig,
) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if c.accessTokenFor(phoneNumberID) == "" {
		return fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}

	templateName := strings.TrimSpace(ui.TemplateName)
	if templateName == "" {
		templateName = strings.TrimSpace(ui.ID)
	}
	if templateName == "" {
		return fmt.Errorf("template_name is empty")
	}

	templateLanguageCode := strings.TrimSpace(ui.TemplateLanguage)
	if templateLanguageCode == "" {
		templateLanguageCode = "es"
	}

	components := make([]templateComponent, 0, len(ui.TemplateComponents))
	for _, component := range ui.TemplateComponents {
		rawType, _ := component["type"].(string)
		componentType := strings.TrimSpace(rawType)
		if componentType == "" {
			continue
		}
		out := templateComponent{
			Type: componentType,
		}
		if rawSubType, ok := component["sub_type"].(string); ok {
			out.SubType = strings.TrimSpace(rawSubType)
		}
		switch idx := component["index"].(type) {
		case string:
			out.Index = strings.TrimSpace(idx)
		case float64:
			out.Index = fmt.Sprintf("%.0f", idx)
		case int:
			out.Index = fmt.Sprintf("%d", idx)
		}
		if rawParams, ok := component["parameters"].([]any); ok {
			out.Parameters = make([]map[string]any, 0, len(rawParams))
			for _, param := range rawParams {
				paramMap, ok := param.(map[string]any)
				if !ok {
					continue
				}
				out.Parameters = append(out.Parameters, paramMap)
			}
		}
		components = append(components, out)
	}

	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "template",
		Template: &templatePayload{
			Name:       templateName,
			Language:   templateLanguage{Code: templateLanguageCode},
			Components: components,
		},
	}

	return c.sendMessage(ctx, phoneNumberID, c.accessTokenFor(phoneNumberID), payload)
}

// DownloadMedia resolves a media ID through Graph API and downloads the raw bytes.
func (c *Client) DownloadMedia(ctx context.Context, phoneNumberID, mediaID string) ([]byte, string, string, error) {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	mediaID = strings.TrimSpace(mediaID)

	if c == nil {
		return nil, "", "", fmt.Errorf("meta outbound client is nil")
	}
	if phoneNumberID == "" {
		return nil, "", "", fmt.Errorf("phone_number_id is empty")
	}
	accessToken := c.accessTokenFor(phoneNumberID)
	if accessToken == "" {
		return nil, "", "", fmt.Errorf("meta outbound access token is empty for phone_number_id=%s", phoneNumberID)
	}
	if mediaID == "" {
		return nil, "", "", fmt.Errorf("media id is empty")
	}

	metadata, err := c.getMediaMetadata(ctx, mediaID, accessToken)
	if err != nil {
		return nil, "", "", err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, metadata.URL, nil)
	if err != nil {
		return nil, "", "", fmt.Errorf("create media download request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, "", "", fmt.Errorf("download media: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, "", "", fmt.Errorf("download media status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", "", fmt.Errorf("read media body: %w", err)
	}
	if len(data) == 0 {
		return nil, "", "", fmt.Errorf("downloaded media is empty")
	}

	contentType := strings.TrimSpace(resp.Header.Get("Content-Type"))
	if contentType == "" {
		contentType = metadata.MimeType
	}

	filename := filenameFromContentDisposition(resp.Header.Get("Content-Disposition"))
	if filename == "" {
		filename = filenameFromMimeType(mediaID, contentType)
	}

	return data, contentType, filename, nil
}

func (c *Client) getMediaMetadata(ctx context.Context, mediaID, accessToken string) (*mediaMetadataResponse, error) {
	url := fmt.Sprintf("%s/%s/%s", c.baseURL, c.apiVersion, mediaID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("create media metadata request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("resolve media metadata: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, fmt.Errorf("resolve media metadata status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	var metadata mediaMetadataResponse
	if err := json.NewDecoder(resp.Body).Decode(&metadata); err != nil {
		return nil, fmt.Errorf("decode media metadata: %w", err)
	}
	if strings.TrimSpace(metadata.URL) == "" {
		return nil, fmt.Errorf("media metadata response missing url")
	}
	return &metadata, nil
}

func filenameFromContentDisposition(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	_, params, err := mime.ParseMediaType(raw)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(params["filename"])
}

func filenameFromMimeType(mediaID, rawMimeType string) string {
	mediaID = strings.TrimSpace(mediaID)
	rawMimeType = strings.TrimSpace(rawMimeType)
	if mediaID == "" {
		mediaID = "media"
	}
	if rawMimeType == "" {
		return mediaID
	}
	if idx := strings.Index(rawMimeType, ";"); idx >= 0 {
		rawMimeType = strings.TrimSpace(rawMimeType[:idx])
	}
	extensions, err := mime.ExtensionsByType(rawMimeType)
	if err != nil || len(extensions) == 0 {
		return mediaID
	}
	return mediaID + extensions[0]
}

func (c *Client) sendMessage(
	ctx context.Context,
	phoneNumberID string,
	accessToken string,
	payload sendMessagePayload,
) error {
	interactiveType := ""
	if payload.Interactive != nil {
		interactiveType = payload.Interactive.Type
	}
	log.Printf(
		"[MetaOutbound] sending type=%s interactive_type=%s to=%s has_context=false",
		payload.Type,
		interactiveType,
		payload.To,
	)

	url := fmt.Sprintf("%s/%s/%s/messages", c.baseURL, c.apiVersion, phoneNumberID)
	rawPayload, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal outbound payload: %w", err)
	}

	var lastErr error
	for attempt := 0; attempt <= c.retryAttempts; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(attempt) * time.Second
			select {
			case <-time.After(backoff):
			case <-ctx.Done():
				return fmt.Errorf("meta outbound canceled while retrying: %w", ctx.Err())
			}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(rawPayload))
		if err != nil {
			lastErr = fmt.Errorf("create request: %w", err)
			continue
		}
		req.Header.Set("Authorization", "Bearer "+accessToken)
		req.Header.Set("Content-Type", "application/json")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("request failed: %w", err)
			continue
		}

		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return nil
		}

		lastErr = fmt.Errorf("meta send status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(respBody)))
		if resp.StatusCode >= 400 && resp.StatusCode < 500 {
			break
		}
	}

	if lastErr == nil {
		lastErr = fmt.Errorf("meta outbound request failed")
	}
	return lastErr
}
