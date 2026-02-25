package metawebhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"testing"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

type fakeSender struct {
	payloads []*webhook.WebhookPayload
	err      error
}

func (f *fakeSender) Send(_ context.Context, payload *webhook.WebhookPayload) (*webhook.WebhookResponse, error) {
	if f.err != nil {
		return nil, f.err
	}
	f.payloads = append(f.payloads, payload)
	return &webhook.WebhookResponse{Success: true}, nil
}

func TestVerifyChallenge(t *testing.T) {
	svc := NewService(Config{
		Enabled:     true,
		VerifyToken: "token-123",
	}, &fakeSender{})

	status, body := svc.VerifyChallenge("subscribe", "token-123", "abc")
	if status != 200 || body != "abc" {
		t.Fatalf("expected 200/abc, got %d/%q", status, body)
	}

	status, _ = svc.VerifyChallenge("subscribe", "bad", "abc")
	if status != 403 {
		t.Fatalf("expected 403 for invalid token, got %d", status)
	}
}

func TestVerifyChallengeDisabled(t *testing.T) {
	svc := NewService(Config{
		Enabled: false,
	}, &fakeSender{})

	status, _ := svc.VerifyChallenge("subscribe", "x", "abc")
	if status != 404 {
		t.Fatalf("expected 404 when disabled, got %d", status)
	}
}

func TestProcessEventValidSignatureRoutesToClientes(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:     true,
		AppSecret:   "secret-1",
		VerifyToken: "token-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs)

	body := []byte(`{
		"object":"whatsapp_business_account",
		"entry":[
			{
				"id":"waba-1",
				"changes":[
					{
						"field":"messages",
						"value":{
							"metadata":{"phone_number_id":"123456789"},
							"messages":[{"from":"593999111222","id":"wamid.1","timestamp":"1730000000","type":"text","text":{"body":"hola"}}]
						}
					}
				]
			}
		]
	}`)
	sig := buildSignature("secret-1", body)

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fs.payloads) != 1 {
		t.Fatalf("expected 1 forwarded payload, got %d", len(fs.payloads))
	}
	got := fs.payloads[0]
	if got.AccountID != "bot-clientes" {
		t.Fatalf("expected account_id bot-clientes, got %s", got.AccountID)
	}
	if got.Phone != "593999111222" {
		t.Fatalf("expected phone 593999111222, got %s", got.Phone)
	}
	if got.Message != "hola" {
		t.Fatalf("expected message hola, got %s", got.Message)
	}
}

func TestProcessEventInvalidSignature(t *testing.T) {
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
	}, &fakeSender{})

	body := []byte(`{"object":"whatsapp_business_account"}`)
	err := svc.ProcessEvent(context.Background(), "sha256=deadbeef", body)
	if !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("expected ErrUnauthorized, got %v", err)
	}
}

func TestProcessEventDisabled(t *testing.T) {
	svc := NewService(Config{
		Enabled: false,
	}, &fakeSender{})

	err := svc.ProcessEvent(context.Background(), "sha256=deadbeef", []byte(`{}`))
	if !errors.Is(err, ErrForbidden) {
		t.Fatalf("expected ErrForbidden, got %v", err)
	}
}

func buildSignature(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}
