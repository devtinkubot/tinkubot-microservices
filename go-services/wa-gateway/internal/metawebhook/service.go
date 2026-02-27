package metawebhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

var (
	// ErrUnauthorized indicates signature verification failure.
	ErrUnauthorized = errors.New("unauthorized")
	// ErrForbidden indicates event rejected by policy.
	ErrForbidden = errors.New("forbidden")
)

// Sender abstracts forwarding payloads to downstream AI services.
type Sender interface {
	Send(ctx context.Context, payload *webhook.WebhookPayload) (*webhook.WebhookResponse, error)
}

// OutboundSender abstracts outbound Meta Cloud API sends.
type OutboundSender interface {
	SendText(ctx context.Context, phoneNumberID, to, body string) error
}

// Config contains runtime settings for Meta webhook processing.
type Config struct {
	Enabled              bool
	VerifyToken          string
	AppSecret            string
	OutboundEnabled      bool
	EnabledAccounts      map[string]bool
	PhoneNumberToAccount map[string]string
}

// Service validates and processes Meta webhook events.
type Service struct {
	cfg            Config
	sender         Sender
	outboundSender OutboundSender
}

// Enabled reports whether webhook processing is active.
func (s *Service) Enabled() bool {
	return s != nil && s.cfg.Enabled
}

// NewService creates a Meta webhook service.
func NewService(cfg Config, sender Sender, outboundSender OutboundSender) *Service {
	if cfg.EnabledAccounts == nil {
		cfg.EnabledAccounts = map[string]bool{}
	}
	if cfg.PhoneNumberToAccount == nil {
		cfg.PhoneNumberToAccount = map[string]string{}
	}
	return &Service{
		cfg:            cfg,
		sender:         sender,
		outboundSender: outboundSender,
	}
}

// VerifyChallenge validates Meta's initial verification challenge.
func (s *Service) VerifyChallenge(mode, verifyToken, challenge string) (int, string) {
	if !s.cfg.Enabled {
		return 404, ""
	}
	if mode != "subscribe" {
		return 403, "forbidden"
	}
	if verifyToken == "" || verifyToken != s.cfg.VerifyToken {
		return 403, "forbidden"
	}
	return 200, challenge
}

// ProcessEvent validates signature and routes inbound messages.
func (s *Service) ProcessEvent(ctx context.Context, signature string, body []byte) error {
	if !s.cfg.Enabled {
		return ErrForbidden
	}
	if !validSignature(signature, body, s.cfg.AppSecret) {
		return ErrUnauthorized
	}

	var evt webhookEvent
	if err := json.Unmarshal(body, &evt); err != nil {
		return fmt.Errorf("invalid payload: %w", err)
	}

	for _, msg := range extractIncomingMessages(evt) {
		accountID, ok := s.cfg.PhoneNumberToAccount[msg.PhoneNumberID]
		if !ok || accountID == "" {
			log.Printf("[MetaWebhook] Unknown phone_number_id=%s, skipping", msg.PhoneNumberID)
			continue
		}
		if len(s.cfg.EnabledAccounts) > 0 && !s.cfg.EnabledAccounts[accountID] {
			log.Printf("[MetaWebhook] Account %s disabled by WA_META_ENABLED_ACCOUNTS", accountID)
			continue
		}

		payload := &webhook.WebhookPayload{
			Phone:      msg.From,
			FromNumber: msg.From + "@s.whatsapp.net",
			Message:    msg.Message,
			Timestamp:  time.Now().Format(time.RFC3339),
			AccountID:  accountID,
		}

		sendCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
		resp, err := s.sender.Send(sendCtx, payload)
		cancel()
		if err != nil {
			log.Printf("[MetaWebhook] Failed forwarding event account=%s from=%s: %v", accountID, msg.From, err)
			continue
		}
		if !resp.Success {
			log.Printf("[MetaWebhook] Downstream returned error account=%s from=%s err=%s", accountID, msg.From, resp.Error)
		}
		if len(resp.Messages) > 0 && s.cfg.OutboundEnabled {
			s.dispatchOutboundReplies(ctx, accountID, msg.PhoneNumberID, msg.From, resp.Messages)
		}
	}

	return nil
}

func (s *Service) dispatchOutboundReplies(
	ctx context.Context,
	accountID, phoneNumberID, to string,
	messages []webhook.ResponseMessage,
) {
	if s.outboundSender == nil {
		log.Printf("[MetaWebhook] Outbound enabled but sender is nil account=%s phone_number_id=%s", accountID, phoneNumberID)
		return
	}
	for idx, reply := range messages {
		body := strings.TrimSpace(reply.Response)
		if body == "" {
			log.Printf("[MetaWebhook] Skipping empty outbound response account=%s index=%d", accountID, idx)
			continue
		}
		sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
		err := s.outboundSender.SendText(sendCtx, phoneNumberID, to, body)
		cancel()
		if err != nil {
			log.Printf("[MetaWebhook] Outbound send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
			continue
		}
		log.Printf("[MetaWebhook] Outbound send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
	}
}

func validSignature(header string, body []byte, appSecret string) bool {
	if appSecret == "" || header == "" {
		return false
	}
	parts := strings.SplitN(header, "=", 2)
	if len(parts) != 2 || parts[0] != "sha256" {
		return false
	}
	got, err := hex.DecodeString(parts[1])
	if err != nil {
		return false
	}
	mac := hmac.New(sha256.New, []byte(appSecret))
	mac.Write(body)
	expected := mac.Sum(nil)
	return hmac.Equal(got, expected)
}
