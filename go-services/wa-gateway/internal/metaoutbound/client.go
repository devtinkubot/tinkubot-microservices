package metaoutbound

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Config struct {
	BaseURL       string
	APIVersion    string
	AccessToken   string
	Timeout       time.Duration
	RetryAttempts int
}

type Client struct {
	baseURL       string
	apiVersion    string
	accessToken   string
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
		retryAttempts: retryAttempts,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

type sendMessagePayload struct {
	MessagingProduct string      `json:"messaging_product"`
	RecipientType    string      `json:"recipient_type,omitempty"`
	To               string      `json:"to"`
	Type             string      `json:"type"`
	Text             textPayload `json:"text"`
}

type textPayload struct {
	PreviewURL bool   `json:"preview_url"`
	Body       string `json:"body"`
}

// SendText sends a plain text WhatsApp message using Meta Cloud API.
func (c *Client) SendText(ctx context.Context, phoneNumberID, to, body string) error {
	phoneNumberID = strings.TrimSpace(phoneNumberID)
	to = strings.TrimSpace(to)
	body = strings.TrimSpace(body)

	if c == nil {
		return fmt.Errorf("meta outbound client is nil")
	}
	if c.accessToken == "" {
		return fmt.Errorf("meta outbound access token is empty")
	}
	if phoneNumberID == "" {
		return fmt.Errorf("phone_number_id is empty")
	}
	if to == "" {
		return fmt.Errorf("destination number is empty")
	}
	if body == "" {
		return fmt.Errorf("message body is empty")
	}

	url := fmt.Sprintf("%s/%s/%s/messages", c.baseURL, c.apiVersion, phoneNumberID)
	payload := sendMessagePayload{
		MessagingProduct: "whatsapp",
		RecipientType:    "individual",
		To:               to,
		Type:             "text",
		Text: textPayload{
			PreviewURL: false,
			Body:       body,
		},
	}

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
		req.Header.Set("Authorization", "Bearer "+c.accessToken)
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
