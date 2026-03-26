package metawebhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
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

type fakeMediaDownloader struct {
	data     []byte
	mimetype string
	filename string
	err      error
	calls    []mediaDownloadCall
}

type mediaDownloadCall struct {
	phoneNumberID string
	mediaID       string
}

type outboundRequest struct {
	kind          string
	phoneNumberID string
	to            string
	body          string
	imageURL      string
	imageCaption  string
	contacts      []webhook.Contact
	options       []webhook.UIOption
	ui            *webhook.UIConfig
}

func (f *fakeMediaDownloader) DownloadMedia(_ context.Context, phoneNumberID, mediaID string) ([]byte, string, string, error) {
	f.calls = append(f.calls, mediaDownloadCall{
		phoneNumberID: phoneNumberID,
		mediaID:       mediaID,
	})
	if f.err != nil {
		return nil, "", "", f.err
	}
	return f.data, f.mimetype, f.filename, nil
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

func (f *fakeOutboundSender) SendContacts(
	_ context.Context,
	phoneNumberID, to string,
	contacts []webhook.Contact,
) error {
	if f.err != nil {
		return f.err
	}
	f.requests = append(f.requests, outboundRequest{
		kind:          "contacts",
		phoneNumberID: phoneNumberID,
		to:            to,
		contacts:      contacts,
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
	}, &fakeSender{}, nil, nil)

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
	}, &fakeSender{}, nil, nil)

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
	}, fs, nil, nil)

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
	}, fs, nil, nil)

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

func TestProcessEventRoutesBotProveedoresInteractiveReply(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"987654321": "bot-proveedores",
		},
	}, fs, nil, nil)

	body := []byte(`{
		"object":"whatsapp_business_account",
		"entry":[
			{
				"id":"waba-1",
				"changes":[
					{
						"field":"messages",
						"value":{
							"metadata":{"phone_number_id":"987654321"},
							"messages":[{"from":"593999111222","id":"wamid.2","timestamp":"1730000001","type":"interactive","interactive":{"type":"button_reply","button_reply":{"id":"availability_accept","title":"Disponible"}}}]
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
	if got.AccountID != "bot-proveedores" {
		t.Fatalf("expected account bot-proveedores, got %s", got.AccountID)
	}
	if got.MessageType != "interactive_button_reply" {
		t.Fatalf("expected message_type interactive_button_reply, got %s", got.MessageType)
	}
	if got.SelectedOption != "availability_accept" {
		t.Fatalf("expected selected_option availability_accept, got %s", got.SelectedOption)
	}
}

func TestProcessEventCapturesReplyContext(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"987654321": "bot-proveedores",
		},
	}, fs, nil, nil)

	body := []byte(`{
		"object":"whatsapp_business_account",
		"entry":[
			{
				"id":"waba-1",
				"changes":[
					{
						"field":"messages",
						"value":{
							"metadata":{"phone_number_id":"987654321"},
							"messages":[{
								"from":"593999111222",
								"id":"wamid.reply.1",
								"timestamp":"1730000001",
								"context":{"from":"593111222333","id":"wamid.template.1"},
								"type":"interactive",
								"interactive":{"type":"button_reply","button_reply":{"id":"availability_accept","title":"Disponible"}}
							}]
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
	if got.ContextFrom != "593111222333" {
		t.Fatalf("expected context_from 593111222333, got %s", got.ContextFrom)
	}
	if got.ContextID != "wamid.template.1" {
		t.Fatalf("expected context_id wamid.template.1, got %s", got.ContextID)
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
	}, fs, nil, nil)

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
	}, fs, nil, nil)

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

func TestProcessEventImageDownloadsMedia(t *testing.T) {
	fs := &fakeSender{}
	media := &fakeMediaDownloader{
		data:     []byte("front-image-bytes"),
		mimetype: "image/jpeg",
		filename: "cedula-frontal.jpg",
	}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-proveedores",
		},
	}, fs, nil, media)

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
							"messages":[{"from":"593999111222","id":"wamid.5","timestamp":"1730000004","type":"image","image":{"id":"1479537139650973","mime_type":"image/jpeg","caption":"frente"}}]
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
	if len(media.calls) != 1 {
		t.Fatalf("expected 1 media download, got %d", len(media.calls))
	}
	if media.calls[0].phoneNumberID != "123456789" || media.calls[0].mediaID != "1479537139650973" {
		t.Fatalf("unexpected media download call: %+v", media.calls[0])
	}
	if len(fs.payloads) != 1 {
		t.Fatalf("expected 1 forwarded payload, got %d", len(fs.payloads))
	}
	got := fs.payloads[0]
	if got.AccountID != "bot-proveedores" {
		t.Fatalf("expected account_id bot-proveedores, got %s", got.AccountID)
	}
	if got.MessageType != "image" || got.Message != "frente" {
		t.Fatalf("unexpected message fields: %+v", got)
	}
	if got.MediaBase64 != "ZnJvbnQtaW1hZ2UtYnl0ZXM=" {
		t.Fatalf("unexpected media_base64: %s", got.MediaBase64)
	}
	if got.MediaMimetype != "image/jpeg" || got.MediaFilename != "cedula-frontal.jpg" {
		t.Fatalf("unexpected media metadata: mimetype=%s filename=%s", got.MediaMimetype, got.MediaFilename)
	}
}

func TestProcessEventDocumentDownloadsMedia(t *testing.T) {
	fs := &fakeSender{}
	media := &fakeMediaDownloader{
		data:     []byte("back-image-bytes"),
		mimetype: "application/pdf",
		filename: "cedula.pdf",
	}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-proveedores",
		},
	}, fs, nil, media)

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
							"messages":[{"from":"593999111222","id":"wamid.6","timestamp":"1730000005","type":"document","document":{"id":"2479537139650973","mime_type":"application/pdf","filename":"cedula.pdf","caption":"reverso"}}]
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
	if got.MessageType != "document" || got.Message != "reverso" {
		t.Fatalf("unexpected message fields: %+v", got)
	}
	if got.MediaBase64 != "YmFjay1pbWFnZS1ieXRlcw==" {
		t.Fatalf("unexpected media_base64: %s", got.MediaBase64)
	}
	if got.MediaMimetype != "application/pdf" || got.MediaFilename != "cedula.pdf" {
		t.Fatalf("unexpected media metadata: mimetype=%s filename=%s", got.MediaMimetype, got.MediaFilename)
	}
}

func TestProcessEventImageDownloadFailureStillForwardsMessage(t *testing.T) {
	fs := &fakeSender{}
	media := &fakeMediaDownloader{
		err: errors.New("graph download failed"),
	}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-proveedores",
		},
	}, fs, nil, media)

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
							"messages":[{"from":"593999111222","id":"wamid.7","timestamp":"1730000006","type":"image","image":{"id":"3479537139650973","mime_type":"image/jpeg","caption":"selfie"}}]
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
	if got.MessageType != "image" || got.Message != "selfie" {
		t.Fatalf("unexpected message fields: %+v", got)
	}
	if got.MediaBase64 != "" || got.MediaMimetype != "" || got.MediaFilename != "" {
		t.Fatalf("expected empty media fields on download failure, got %+v", got)
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
	}, fs, nil, nil)

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
	}, &fakeSender{}, nil, nil)

	body := []byte(`{"object":"whatsapp_business_account"}`)
	err := svc.ProcessEvent(context.Background(), "sha256=deadbeef", body)
	if !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("expected ErrUnauthorized, got %v", err)
	}
}

func TestProcessEventDisabled(t *testing.T) {
	svc := NewService(Config{
		Enabled: false,
	}, &fakeSender{}, nil, nil)

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
	}, fs, fo, nil)

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
	}, fs, fo, nil)

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

func TestProcessEventOutboundContactsReply(t *testing.T) {
	fs := &fakeSender{}
	fo := &fakeOutboundSender{}
	svc := NewService(Config{
		Enabled:         true,
		AppSecret:       "secret-1",
		OutboundEnabled: true,
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, fo, nil)

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
				Contacts: []webhook.Contact{
					{
						Name: webhook.ContactName{
							FormattedName: "Diego Unkuch Gonzalez",
							FirstName:     "Diego",
						},
						Phones: []webhook.ContactPhone{
							{
								Phone: "+593959091325",
								Type:  "CELL",
								WAID:  "593959091325",
							},
						},
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
	if fo.requests[0].kind != "contacts" {
		t.Fatalf("expected contacts outbound kind, got %+v", fo.requests[0])
	}
	if len(fo.requests[0].contacts) != 1 || fo.requests[0].contacts[0].Phones[0].WAID != "593959091325" {
		t.Fatalf("unexpected contact outbound payload: %+v", fo.requests[0].contacts)
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
	}, fs, fo, nil)

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
	}, fs, fo, nil)

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
	}, fs, fo, nil)

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
	}, fs, fo, nil)

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
	}, fs, fo, nil)

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

func TestRedactInboundPayload(t *testing.T) {
	raw := []byte(`{
		"entry":[{
			"changes":[{
				"value":{
					"metadata":{"phone_number_id":"987654321"},
					"messages":[{
						"from":"593999111222",
						"context":{"from":"593111222333","id":"wamid.template.1"},
						"type":"text",
						"text":{"body":"acepto"}
					}]
				}
			}]
		}]
	}`)

	redacted := redactInboundPayload(raw, 4096)
	for _, expected := range []string{
		`"phone_number_id":"987654321"`,
		`"from":"593999111222"`,
		`"context":{"from":"593111222333","id":"wamid.template.1"}`,
		`"body":"\u003credacted\u003e"`,
	} {
		if !contains(redacted, expected) {
			t.Fatalf("expected redacted payload to contain %s, got %s", expected, redacted)
		}
	}
	if contains(redacted, `"body":"acepto"`) {
		t.Fatalf("expected redacted payload to hide text body, got %s", redacted)
	}
}

func contains(haystack, needle string) bool {
	return strings.Contains(haystack, needle)
}

func buildSignature(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}

func TestProcessEventBSUIDWithFallback(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, nil)

	// Test with BSUID present
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
							"contacts":[{
								"profile":{"name":"Test User","formatted_name":"Test User Formatted","first_name":"Test","last_name":"User","username":"testuser","country_code":"US"},
								"wa_id":"593999111222",
								"user_id":"user.9373795779eb6441c8adb2eaee5b848e7dd174ddd302d7db62142f4722d574b6"
							}],
							"messages":[{
								"from":"593999111222",
								"from_user_id":"user.abc123def456",
								"id":"wamid.1",
								"timestamp":"1730000000",
								"type":"text",
								"text":{"body":"hola"}
							}]
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
	// Phone should be the BSUID when available
	if got.Phone != "user.abc123def456" {
		t.Fatalf("expected phone to be BSUID user.abc123def456, got %s", got.Phone)
	}
	// UserID should be set
	if got.UserID != "user.abc123def456" {
		t.Fatalf("expected user_id user.abc123def456, got %s", got.UserID)
	}
	// Username should be extracted from contact
	if got.Username != "testuser" {
		t.Fatalf("expected username testuser, got %s", got.Username)
	}
	// DisplayName should be extracted from contact name
	if got.DisplayName != "Test User Formatted" {
		t.Fatalf("expected display_name Test User Formatted, got %s", got.DisplayName)
	}
	// FormattedName, FirstName and LastName should be extracted from contact
	if got.FormattedName != "Test User Formatted" {
		t.Fatalf("expected formatted_name Test User Formatted, got %s", got.FormattedName)
	}
	if got.FirstName != "Test" {
		t.Fatalf("expected first_name Test, got %s", got.FirstName)
	}
	if got.LastName != "User" {
		t.Fatalf("expected last_name User, got %s", got.LastName)
	}
	// CountryCode should be extracted from contact
	if got.CountryCode != "US" {
		t.Fatalf("expected country_code US, got %s", got.CountryCode)
	}
	// FromNumber should still be the original phone number
	if got.FromNumber != "593999111222@s.whatsapp.net" {
		t.Fatalf("expected from_number 593999111222@s.whatsapp.net, got %s", got.FromNumber)
	}
}

func TestProcessEventBSUIDWithoutFromField(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, nil)

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
							"contacts":[{
								"profile":{"name":"Test User","formatted_name":"Test User Formatted","first_name":"Test","last_name":"User","username":"testuser","country_code":"US"},
								"user_id":"US.13491208655302741918"
							}],
							"messages":[{
								"from_user_id":"US.13491208655302741918",
								"id":"wamid.bsuid.1",
								"timestamp":"1730000005",
								"type":"text",
								"text":{"body":"hola"}
							}]
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
	if got.Phone != "US.13491208655302741918" {
		t.Fatalf("expected phone to use BSUID fallback, got %s", got.Phone)
	}
	if got.UserID != "US.13491208655302741918" {
		t.Fatalf("expected user_id US.13491208655302741918, got %s", got.UserID)
	}
	if got.FromNumber != "US.13491208655302741918@lid" {
		t.Fatalf("expected from_number US.13491208655302741918@lid, got %s", got.FromNumber)
	}
	if got.DisplayName != "Test User Formatted" {
		t.Fatalf("expected display_name Test User Formatted, got %s", got.DisplayName)
	}
}

func TestProcessEventBSUIDFallbackToContact(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, nil)

	// Test with BSUID only in contact, not in message
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
							"contacts":[{
								"profile":{"name":"Test User"},
								"wa_id":"593999111222",
								"user_id":"user.from.contact"
							}],
							"messages":[{
								"from":"593999111222",
								"id":"wamid.1",
								"timestamp":"1730000000",
								"type":"text",
								"text":{"body":"hola"}
							}]
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
	// Phone should be the contact's BSUID when message doesn't have from_user_id
	if got.Phone != "user.from.contact" {
		t.Fatalf("expected phone to be BSUID user.from.contact, got %s", got.Phone)
	}
	if got.UserID != "user.from.contact" {
		t.Fatalf("expected user_id user.from.contact, got %s", got.UserID)
	}
}

func TestProcessEventNoBSUIDFallbackToPhone(t *testing.T) {
	fs := &fakeSender{}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, nil)

	// Test without BSUID - should fallback to phone number
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
							"contacts":[{
								"profile":{"name":"Test User"},
								"wa_id":"593999111222"
							}],
							"messages":[{
								"from":"593999111222",
								"id":"wamid.1",
								"timestamp":"1730000000",
								"type":"text",
								"text":{"body":"hola"}
							}]
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
	// Phone should fallback to the original phone number
	if got.Phone != "593999111222" {
		t.Fatalf("expected phone to fallback to 593999111222, got %s", got.Phone)
	}
	// UserID should be empty
	if got.UserID != "" {
		t.Fatalf("expected user_id to be empty, got %s", got.UserID)
	}
}

func TestProcessEventAudioMessage(t *testing.T) {
	fs := &fakeSender{}
	media := &fakeMediaDownloader{
		data:     []byte("audio-bytes"),
		mimetype: "audio/ogg",
		filename: "",
	}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, media)

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
							"messages":[{
								"from":"593999111222",
								"id":"wamid.audio.1",
								"timestamp":"1730000000",
								"type":"audio",
								"audio":{"id":"audio123","mime_type":"audio/ogg"}
							}]
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
	if got.MessageType != "audio" {
		t.Fatalf("expected message_type audio, got %s", got.MessageType)
	}
	if got.MediaMimetype != "audio/ogg" {
		t.Fatalf("expected media_mimetype audio/ogg, got %s", got.MediaMimetype)
	}
	if got.MediaBase64 != "YXVkaW8tYnl0ZXM=" {
		t.Fatalf("expected media_base64 YXVkaW8tYnl0ZXM=, got %s", got.MediaBase64)
	}
}

func TestProcessEventVideoMessage(t *testing.T) {
	fs := &fakeSender{}
	media := &fakeMediaDownloader{
		data:     []byte("video-bytes"),
		mimetype: "video/mp4",
		filename: "",
	}
	svc := NewService(Config{
		Enabled:   true,
		AppSecret: "secret-1",
		PhoneNumberToAccount: map[string]string{
			"123456789": "bot-clientes",
		},
	}, fs, nil, media)

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
							"messages":[{
								"from":"593999111222",
								"id":"wamid.video.1",
								"timestamp":"1730000000",
								"type":"video",
								"video":{"id":"video123","mime_type":"video/mp4","caption":"Mira este video"}
							}]
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
	if got.MessageType != "video" {
		t.Fatalf("expected message_type video, got %s", got.MessageType)
	}
	if got.Message != "Mira este video" {
		t.Fatalf("expected message 'Mira este video', got %s", got.Message)
	}
	if got.MediaMimetype != "video/mp4" {
		t.Fatalf("expected media_mimetype video/mp4, got %s", got.MediaMimetype)
	}
}
