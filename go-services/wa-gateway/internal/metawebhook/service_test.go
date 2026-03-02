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
	resp     *webhook.WebhookResponse
}

func (f *fakeSender) Send(_ context.Context, payload *webhook.WebhookPayload) (*webhook.WebhookResponse, error) {
	if f.err != nil {
		return nil, f.err
	}
	f.payloads = append(f.payloads, payload)
	if f.resp != nil {
		return f.resp, nil
	}
	return &webhook.WebhookResponse{Success: true}, nil
}

type fakeOutboundSender struct {
	requests []outboundRequest
	err      error
}

type outboundRequest struct {
	kind          string
	phoneNumberID string
	to            string
	body          string
	imageURL      string
	imageCaption  string
	options       []webhook.UIOption
	ui            *webhook.UIConfig
}

func (f *fakeOutboundSender) SendText(_ context.Context, phoneNumberID, to, body string) error {
	if f.err != nil {
		return f.err
	}
	f.requests = append(f.requests, outboundRequest{
		kind:          "text",
		phoneNumberID: phoneNumberID,
		to:            to,
		body:          body,
	})
	return nil
}

func (f *fakeOutboundSender) SendImage(_ context.Context, phoneNumberID, to, imageURL, caption string) error {
	if f.err != nil {
		return f.err
	}
	f.requests = append(f.requests, outboundRequest{
		kind:          "image",
		phoneNumberID: phoneNumberID,
		to:            to,
		imageURL:      imageURL,
		imageCaption:  caption,
	})
	return nil
}

func (f *fakeOutboundSender) SendButtons(
	_ context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	if f.err != nil {
		return f.err
	}
	copyUI := ui
	f.requests = append(f.requests, outboundRequest{
		kind:          "buttons",
		phoneNumberID: phoneNumberID,
		to:            to,
		body:          body,
		options:       ui.Options,
		ui:            &copyUI,
	})
	return nil
}

func (f *fakeOutboundSender) SendList(
	_ context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	if f.err != nil {
		return f.err
	}
	copyUI := ui
	f.requests = append(f.requests, outboundRequest{
		kind:          "list",
		phoneNumberID: phoneNumberID,
		to:            to,
		body:          body,
		options:       ui.Options,
		ui:            &copyUI,
	})
	return nil
}

func (f *fakeOutboundSender) SendLocationRequest(
	_ context.Context,
	phoneNumberID, to, body string,
) error {
	if f.err != nil {
		return f.err
	}
	f.requests = append(f.requests, outboundRequest{
		kind:          "location_request",
		phoneNumberID: phoneNumberID,
		to:            to,
		body:          body,
	})
	return nil
}

func (f *fakeOutboundSender) SendFlow(
	_ context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	if f.err != nil {
		return f.err
	}
	copyUI := ui
	f.requests = append(f.requests, outboundRequest{
		kind:          "flow",
		phoneNumberID: phoneNumberID,
		to:            to,
		body:          body,
		ui:            &copyUI,
	})
	return nil
}

func (f *fakeOutboundSender) SendTemplate(
	_ context.Context,
	phoneNumberID, to string,
	ui webhook.UIConfig,
) error {
	if f.err != nil {
		return f.err
	}
	copyUI := ui
	f.requests = append(f.requests, outboundRequest{
		kind:          "template",
		phoneNumberID: phoneNumberID,
		to:            to,
		ui:            &copyUI,
	})
	return nil
}

func TestVerifyChallenge(t *testing.T) {
	svc := NewService(Config{
		Enabled:     true,
		VerifyToken: "token-123",
	}, &fakeSender{}, nil)

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
	}, &fakeSender{}, nil)

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
	}, fs, nil)

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
	if got.Message != "hola" || got.Content != "hola" {
		t.Fatalf("expected message/content hola, got message=%s content=%s", got.Message, got.Content)
	}
	if got.MessageType != "text" {
		t.Fatalf("expected message_type text, got %s", got.MessageType)
	}
}

func TestProcessEventInteractiveButtonReply(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil)

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
							"messages":[{"from":"593999111222","id":"wamid.2","timestamp":"1730000001","type":"interactive","interactive":{"type":"button_reply","button_reply":{"id":"problem_confirm_yes","title":"Sí, correcto"}}}]
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
	if got.MessageType != "interactive_button_reply" {
		t.Fatalf("expected message_type interactive_button_reply, got %s", got.MessageType)
	}
	if got.SelectedOption != "problem_confirm_yes" {
		t.Fatalf("expected selected_option problem_confirm_yes, got %s", got.SelectedOption)
	}
	if got.Content != "" {
		t.Fatalf("expected empty content for interactive reply, got %s", got.Content)
	}
}

func TestProcessEventInteractiveButtonReplyFallbackTitle(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil)

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
							"messages":[{"from":"593999111222","id":"wamid.2","timestamp":"1730000001","type":"interactive","interactive":{"type":"button_reply","button_reply":{"id":"","title":"Continuar"}}}]
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
	if got.MessageType != "interactive_button_reply" {
		t.Fatalf("expected message_type interactive_button_reply, got %s", got.MessageType)
	}
	if got.SelectedOption != "continuar" {
		t.Fatalf("expected selected_option continuar, got %s", got.SelectedOption)
	}
}

func TestProcessEventLocation(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil)

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
							"messages":[{"from":"593999111222","id":"wamid.3","timestamp":"1730000002","type":"location","location":{"latitude":-0.18,"longitude":-78.47,"name":"Mi ubicación","address":"Quito"}}]
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
	if got.MessageType != "location" {
		t.Fatalf("expected message_type location, got %s", got.MessageType)
	}
	if got.Location == nil {
		t.Fatalf("expected location payload")
	}
	if got.Location.Latitude != -0.18 || got.Location.Longitude != -78.47 {
		t.Fatalf("unexpected location payload: %+v", got.Location)
	}
}

func TestProcessEventInteractiveFlowReply(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil)

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
							"messages":[{"from":"593999111222","id":"wamid.4","timestamp":"1730000003","type":"interactive","interactive":{"type":"nfm_reply","nfm_reply":{"name":"flow","response_json":{"consent_accepted":true,"city":"Cuenca"}}}}]
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
	if got.MessageType != "interactive_flow_reply" {
		t.Fatalf("expected message_type interactive_flow_reply, got %s", got.MessageType)
	}
	if got.FlowPayload == nil {
		t.Fatalf("expected flow payload")
	}
	if city, _ := got.FlowPayload["city"].(string); city != "Cuenca" {
		t.Fatalf("expected city Cuenca in flow payload, got %+v", got.FlowPayload)
	}
}

func TestProcessEventInvalidSignature(t *testing.T) {
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
	}, &fakeSender{}, nil)

	body := []byte(`{"object":"whatsapp_business_account"}`)
	err := svc.ProcessEvent(context.Background(), "sha256=deadbeef", body)
	if !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("expected ErrUnauthorized, got %v", err)
	}
}

func TestProcessEventDisabled(t *testing.T) {
	svc := NewService(Config{
		Enabled: false,
	}, &fakeSender{}, nil)

	err := svc.ProcessEvent(context.Background(), "sha256=deadbeef", []byte(`{}`))
	if !errors.Is(err, ErrForbidden) {
		t.Fatalf("expected ErrForbidden, got %v", err)
	}
}

func TestProcessEventOutboundEnabledSendsReplies(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{Response: "respuesta 1"},
			{Response: "respuesta 2"},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 2 {
		t.Fatalf("expected 2 outbound sends, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "text" || fo.requests[0].phoneNumberID != "123456789" || fo.requests[0].to != "593999111222" || fo.requests[0].body != "respuesta 1" {
		t.Fatalf("unexpected first outbound request: %+v", fo.requests[0])
	}
}

func TestProcessEventOutboundEnabledSendsImageReply(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				Response:     "Texto onboarding",
				MediaURL:     "https://example.com/onboarding.png",
				MediaType:    "image",
				MediaCaption: "",
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound send, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "image" {
		t.Fatalf("expected image outbound kind, got %+v", fo.requests[0])
	}
	if fo.requests[0].imageURL != "https://example.com/onboarding.png" {
		t.Fatalf("expected image url, got %+v", fo.requests[0])
	}
	if fo.requests[0].imageCaption != "Texto onboarding" {
		t.Fatalf("expected image caption, got %+v", fo.requests[0])
	}
}

func TestProcessEventOutboundEnabledSendsFlowReply(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				Response: "Completa tu onboarding",
				UI: &webhook.UIConfig{
					Type:       "flow",
					FlowID:     "flow-onboarding-1",
					FlowCTA:    "Empezar",
					FlowMode:   "published",
					FlowAction: "navigate",
				},
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound request, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "flow" {
		t.Fatalf("expected flow outbound kind, got %s", fo.requests[0].kind)
	}
	if fo.requests[0].ui == nil || fo.requests[0].ui.FlowID != "flow-onboarding-1" {
		t.Fatalf("expected flow ui with flow_id, got %+v", fo.requests[0].ui)
	}
}

func TestProcessEventOutboundButtons(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				Response: "¿Confirmas este problema?",
				UI: &webhook.UIConfig{
					Type:           "buttons",
					HeaderType:     "image",
					HeaderMediaURL: "https://example.com/onboarding.png",
					Options: []webhook.UIOption{
						{ID: "problem_confirm_yes", Title: "Sí, correcto"},
						{ID: "problem_confirm_no", Title: "No, corregir"},
					},
				},
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound send, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "buttons" {
		t.Fatalf("expected buttons outbound, got %+v", fo.requests[0])
	}
	if len(fo.requests[0].options) != 2 {
		t.Fatalf("expected 2 options, got %d", len(fo.requests[0].options))
	}
	if fo.requests[0].ui == nil || fo.requests[0].ui.HeaderType != "image" {
		t.Fatalf("expected image header in buttons ui, got %+v", fo.requests[0].ui)
	}
}

func TestProcessEventOutboundLocationRequest(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				Response: "Comparte tu ubicación para continuar.",
				UI: &webhook.UIConfig{
					Type: "location_request",
					ID:   "request_location_v1",
				},
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound send, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "location_request" {
		t.Fatalf("expected location_request outbound, got %+v", fo.requests[0])
	}
}

func TestProcessEventOutboundList(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				Response: "¿Qué necesitas resolver?. Describe lo que necesitas.",
				UI: &webhook.UIConfig{
					Type:             "list",
					ListButtonText:   "Ver servicios populares",
					ListSectionTitle: "Más solicitados",
					Options: []webhook.UIOption{
						{ID: "plomero", Title: "Plomero"},
						{ID: "electricista", Title: "Electricista"},
					},
				},
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound send, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "list" {
		t.Fatalf("expected list outbound, got %+v", fo.requests[0])
	}
	if len(fo.requests[0].options) != 2 {
		t.Fatalf("expected 2 list options, got %d", len(fo.requests[0].options))
	}
}

func TestProcessEventOutboundTemplate(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo)

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
	fs.resp = &webhook.WebhookResponse{
		Success: true,
		Messages: []webhook.ResponseMessage{
			{
				UI: &webhook.UIConfig{
					Type:             "template",
					TemplateName:     "tinkubot_onboarding_precontractual_v1",
					TemplateLanguage: "es",
					TemplateComponents: []map[string]any{
						{"type": "header"},
					},
				},
			},
		},
	}

	if err := svc.ProcessEvent(context.Background(), sig, body); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(fo.requests) != 1 {
		t.Fatalf("expected 1 outbound send, got %d", len(fo.requests))
	}
	if fo.requests[0].kind != "template" {
		t.Fatalf("expected template outbound, got %+v", fo.requests[0])
	}
	if fo.requests[0].ui == nil || fo.requests[0].ui.TemplateName != "tinkubot_onboarding_precontractual_v1" {
		t.Fatalf("expected template ui with name, got %+v", fo.requests[0].ui)
	}
}

func buildSignature(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}
