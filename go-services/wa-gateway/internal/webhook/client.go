package webhook

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

// Send sends payload to the AI service with retry logic
// Routes dynamically based on payload.AccountID
func (wc *WebhookClient) Send(ctx context.Context, payload *WebhookPayload) (*WebhookResponse, error) {
	var lastErr error
	url := wc.getURL(payload.AccountID)

	for attempt := 0; attempt <= wc.retryAttempts; attempt++ {
		if attempt > 0 {
			log.Printf("[Webhook] Retry %d/%d for %s", attempt, wc.retryAttempts, payload.AccountID)
			backoff := time.Duration(attempt) * time.Second
			select {
			case <-time.After(backoff):
			case <-ctx.Done():
				return nil, fmt.Errorf("request canceled while retrying webhook: %w", ctx.Err())
			}
		}

		jsonData, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("error marshaling payload: %w", err)
		}

		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
		if err != nil {
			lastErr = fmt.Errorf("error creating request: %w", err)
			continue
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("User-Agent", "wa-gateway/1.0")
		req.Header.Set("X-Account-ID", payload.AccountID)

		resp, err := wc.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("request failed: %w", err)
			continue
		}

		if resp.StatusCode != http.StatusOK {
			lastErr = fmt.Errorf("unexpected status code: %d", resp.StatusCode)
			resp.Body.Close()
			continue
		}

		var webhookResp WebhookResponse
		if err := json.NewDecoder(resp.Body).Decode(&webhookResp); err != nil {
			resp.Body.Close()
			return nil, fmt.Errorf("error decoding response: %w", err)
		}
		resp.Body.Close()

		log.Printf("[Webhook] Message sent successfully to %s (account: %s)", url, payload.AccountID)
		return &webhookResp, nil
	}

	return nil, fmt.Errorf("failed after %d attempts for %s: %w", wc.retryAttempts+1, payload.AccountID, lastErr)
}
