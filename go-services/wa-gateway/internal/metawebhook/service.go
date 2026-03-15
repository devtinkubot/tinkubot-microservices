package metawebhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
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
	SendImage(ctx context.Context, phoneNumberID, to, imageURL, caption string) error
	SendContacts(ctx context.Context, phoneNumberID, to string, contacts []webhook.Contact) error
	SendButtons(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendList(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendLocationRequest(ctx context.Context, phoneNumberID, to, body string) error
	SendFlow(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendTemplate(ctx context.Context, phoneNumberID, to string, ui webhook.UIConfig) error
}

// MediaDownloader resolves inbound Meta media ids into raw bytes.
type MediaDownloader interface {
	DownloadMedia(ctx context.Context, phoneNumberID, mediaID string) ([]byte, string, string, error)
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
	cfg             Config
	sender          Sender
	outboundSender  OutboundSender
	mediaDownloader MediaDownloader
}

// Enabled reports whether webhook processing is active.
func (s *Service) Enabled() bool {
	return s != nil && s.cfg.Enabled
}

// NewService creates a Meta webhook service.
func NewService(cfg Config, sender Sender, outboundSender OutboundSender, mediaDownloader MediaDownloader) *Service {
	if cfg.EnabledAccounts == nil {
		cfg.EnabledAccounts = map[string]bool{}
	}
	if cfg.PhoneNumberToAccount == nil {
		cfg.PhoneNumberToAccount = map[string]string{}
	}
	return &Service{
		cfg:             cfg,
		sender:          sender,
		outboundSender:  outboundSender,
		mediaDownloader: mediaDownloader,
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
			Phone:          msg.From,
			FromNumber:     msg.From + "@s.whatsapp.net",
			Content:        msg.Content,
			Message:        msg.Content,
			MessageType:    msg.MessageType,
			SelectedOption: msg.SelectedOption,
			FlowPayload:    msg.FlowPayload,
			Timestamp:      time.Now().Format(time.RFC3339),
			AccountID:      accountID,
		}
		if msg.Location != nil {
			payload.Location = &webhook.LocationPayload{
				Latitude:  msg.Location.Latitude,
				Longitude: msg.Location.Longitude,
				Name:      msg.Location.Name,
				Address:   msg.Location.Address,
			}
		}
		if msg.MediaID != "" {
			if s.mediaDownloader == nil {
				log.Printf("[MetaWebhook] Media downloader is nil account=%s phone_number_id=%s from=%s message_type=%s media_id=%s", accountID, msg.PhoneNumberID, msg.From, msg.MessageType, msg.MediaID)
			} else {
				mediaCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
				data, mimetype, filename, err := s.mediaDownloader.DownloadMedia(mediaCtx, msg.PhoneNumberID, msg.MediaID)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Failed downloading media account=%s phone_number_id=%s from=%s message_type=%s media_id=%s err=%v", accountID, msg.PhoneNumberID, msg.From, msg.MessageType, msg.MediaID, err)
				} else {
					payload.MediaBase64 = base64.StdEncoding.EncodeToString(data)
					if mimetype != "" {
						payload.MediaMimetype = mimetype
					} else {
						payload.MediaMimetype = msg.MediaMimetype
					}
					if filename != "" {
						payload.MediaFilename = filename
					} else {
						payload.MediaFilename = msg.MediaFilename
					}
				}
			}
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
		outboundMessages := normalizeOutboundMessages(resp)
		if len(outboundMessages) > 0 && s.cfg.OutboundEnabled {
			s.dispatchOutboundReplies(ctx, accountID, msg.PhoneNumberID, msg.From, outboundMessages)
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
		imageURL := strings.TrimSpace(reply.MediaURL)
		imageCaption := strings.TrimSpace(reply.MediaCaption)
		mediaType := strings.ToLower(strings.TrimSpace(reply.MediaType))
		if len(reply.Contacts) > 0 {
			sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
			err := s.outboundSender.SendContacts(sendCtx, phoneNumberID, to, reply.Contacts)
			cancel()
			if err != nil {
				log.Printf("[MetaWebhook] Outbound contacts send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
				continue
			}
			log.Printf("[MetaWebhook] Outbound contacts send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
			if body == "" && reply.UI == nil && imageURL == "" {
				continue
			}
		}
		if imageURL != "" && (mediaType == "" || mediaType == "image") {
			if imageCaption == "" {
				imageCaption = body
			}
			sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
			err := s.outboundSender.SendImage(sendCtx, phoneNumberID, to, imageURL, imageCaption)
			cancel()
			if err != nil {
				log.Printf("[MetaWebhook] Outbound image send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
				continue
			}
			log.Printf("[MetaWebhook] Outbound image send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
			if reply.UI == nil {
				if imageCaption == body {
					continue
				}
				if body == "" {
					continue
				}
			}
		}
		if reply.UI != nil {
			uiType := strings.TrimSpace(reply.UI.Type)
			switch uiType {
			case "buttons":
				if body == "" {
					log.Printf("[MetaWebhook] Skipping buttons outbound with empty body account=%s index=%d", accountID, idx)
					continue
				}
				sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
				err := s.outboundSender.SendButtons(sendCtx, phoneNumberID, to, body, *reply.UI)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Outbound buttons send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
					continue
				}
				log.Printf("[MetaWebhook] Outbound buttons send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
				continue
			case "list":
				if body == "" {
					log.Printf("[MetaWebhook] Skipping list outbound with empty body account=%s index=%d", accountID, idx)
					continue
				}
				sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
				err := s.outboundSender.SendList(sendCtx, phoneNumberID, to, body, *reply.UI)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Outbound list send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
					continue
				}
				log.Printf("[MetaWebhook] Outbound list send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
				continue
			case "location_request":
				if body == "" {
					body = "Comparte tu ubicación para continuar."
				}
				sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
				err := s.outboundSender.SendLocationRequest(sendCtx, phoneNumberID, to, body)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Outbound location request send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
					continue
				}
				log.Printf("[MetaWebhook] Outbound location request send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
				continue
			case "flow":
				sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
				err := s.outboundSender.SendFlow(sendCtx, phoneNumberID, to, body, *reply.UI)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Outbound flow send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
					continue
				}
				log.Printf("[MetaWebhook] Outbound flow send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
				continue
			case "template":
				sendCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
				err := s.outboundSender.SendTemplate(sendCtx, phoneNumberID, to, *reply.UI)
				cancel()
				if err != nil {
					log.Printf("[MetaWebhook] Outbound template send failed account=%s phone_number_id=%s to=%s index=%d err=%v", accountID, phoneNumberID, to, idx, err)
					continue
				}
				log.Printf("[MetaWebhook] Outbound template send ok account=%s phone_number_id=%s to=%s index=%d", accountID, phoneNumberID, to, idx)
				continue
			default:
				log.Printf("[MetaWebhook] Unsupported ui.type=%s account=%s index=%d, fallback text", uiType, accountID, idx)
			}
		}
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

func normalizeOutboundMessages(resp *webhook.WebhookResponse) []webhook.ResponseMessage {
	if resp == nil || len(resp.Messages) == 0 {
		return nil
	}
	out := make([]webhook.ResponseMessage, len(resp.Messages))
	copy(out, resp.Messages)

	if resp.UI == nil {
		return out
	}
	hasMessageUI := false
	for _, msg := range out {
		if msg.UI != nil {
			hasMessageUI = true
			break
		}
	}
	if !hasMessageUI {
		out[0].UI = resp.UI
	}
	return out
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
