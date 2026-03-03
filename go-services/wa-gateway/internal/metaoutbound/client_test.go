package metaoutbound

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

func TestSendTextSuccess(t *testing.T) {
	var gotPath string
	var gotAuth string
	var gotPayload sendMessagePayload

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotAuth = r.Header.Get("Authorization")
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendText(context.Background(), "1022104724314763", "593998823053", "hola")
	if err != nil {
		t.Fatalf("SendText returned error: %v", err)
	}

	if gotPath != "/v22.0/1022104724314763/messages" {
		t.Fatalf("unexpected path: %s", gotPath)
	}
	if gotAuth != "Bearer token-123" {
		t.Fatalf("unexpected auth header: %s", gotAuth)
	}
	if gotPayload.MessagingProduct != "whatsapp" || gotPayload.Type != "text" || gotPayload.To != "593998823053" || gotPayload.Text == nil || gotPayload.Text.Body != "hola" {
		t.Fatalf("unexpected payload: %+v", gotPayload)
	}
}

func TestSendButtonsSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendButtons(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"¿Confirmas este problema?",
		webhook.UIConfig{
			Type:           "buttons",
			HeaderType:     "image",
			HeaderMediaURL: "https://example.com/header.png",
			FooterText:     "Al continuar aceptas nuestra política de datos.",
			Options: []webhook.UIOption{
				{ID: "problem_confirm_yes", Title: "Sí, correcto"},
				{ID: "problem_confirm_no", Title: "No, corregir"},
			},
		},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}

	if gotPayload.Type != "interactive" || gotPayload.Interactive == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Interactive.Type != "button" {
		t.Fatalf("expected interactive button, got %+v", gotPayload.Interactive)
	}
	if gotPayload.Interactive.Header == nil || gotPayload.Interactive.Header.Type != "image" {
		t.Fatalf("expected image header, got %+v", gotPayload.Interactive.Header)
	}
	if gotPayload.Interactive.Footer == nil || gotPayload.Interactive.Footer.Text == "" {
		t.Fatalf("expected footer text, got %+v", gotPayload.Interactive.Footer)
	}
	if len(gotPayload.Interactive.Action.Buttons) != 2 {
		t.Fatalf("expected 2 buttons, got %d", len(gotPayload.Interactive.Action.Buttons))
	}
}

func TestSendListSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendList(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"¿Qué necesitas resolver?. Describe lo que necesitas.",
		webhook.UIConfig{
			Type:             "list",
			ListButtonText:   "Ver servicios populares",
			ListSectionTitle: "Más solicitados",
			Options: []webhook.UIOption{
				{ID: "plomero", Title: "Top 1:", Description: "Plomero"},
				{ID: "electricista", Title: "Top 2:", Description: "Electricista"},
			},
		},
	)
	if err != nil {
		t.Fatalf("SendList returned error: %v", err)
	}

	if gotPayload.Type != "interactive" || gotPayload.Interactive == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Interactive.Type != "list" {
		t.Fatalf("expected interactive list, got %+v", gotPayload.Interactive)
	}
	if gotPayload.Interactive.Action.Button != "Ver servicios populares" {
		t.Fatalf("unexpected list button text: %+v", gotPayload.Interactive.Action)
	}
	if len(gotPayload.Interactive.Action.Sections) != 1 {
		t.Fatalf("expected 1 section, got %+v", gotPayload.Interactive.Action.Sections)
	}
	if len(gotPayload.Interactive.Action.Sections[0].Rows) != 2 {
		t.Fatalf("expected 2 rows, got %+v", gotPayload.Interactive.Action.Sections[0].Rows)
	}
	if gotPayload.Interactive.Action.Sections[0].Rows[0].Description != "Plomero" {
		t.Fatalf("unexpected row description: %+v", gotPayload.Interactive.Action.Sections[0].Rows[0])
	}
}

func TestSendButtonsFooterTooLongIsTruncated(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	longFooter := "Al continuar aceptas el tratamiento de datos según nuestra política de privacidad vigente."
	err := client.SendButtons(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"Mensaje",
		webhook.UIConfig{
			Type:       "buttons",
			FooterText: longFooter,
			Options: []webhook.UIOption{
				{ID: "continue_onboarding", Title: "Continuar"},
			},
		},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}

	if gotPayload.Interactive == nil || gotPayload.Interactive.Footer == nil {
		t.Fatalf("expected footer in payload, got %+v", gotPayload.Interactive)
	}
	if len([]rune(gotPayload.Interactive.Footer.Text)) != 60 {
		t.Fatalf("expected truncated footer len 60, got %d (%q)", len([]rune(gotPayload.Interactive.Footer.Text)), gotPayload.Interactive.Footer.Text)
	}
}

func TestSendButtonsEmptyFooterIsOmitted(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendButtons(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"Mensaje",
		webhook.UIConfig{
			Type:       "buttons",
			FooterText: "    ",
			Options: []webhook.UIOption{
				{ID: "continue_onboarding", Title: "Continuar"},
			},
		},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}

	if gotPayload.Interactive == nil {
		t.Fatalf("expected interactive payload")
	}
	if gotPayload.Interactive.Footer != nil {
		t.Fatalf("expected footer omitted, got %+v", gotPayload.Interactive.Footer)
	}
}

func TestSendImageSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendImage(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"https://example.com/logo.png",
		"TinkuBot",
	)
	if err != nil {
		t.Fatalf("SendImage returned error: %v", err)
	}

	if gotPayload.Type != "image" || gotPayload.Image == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Image.Link != "https://example.com/logo.png" {
		t.Fatalf("unexpected image link: %+v", gotPayload.Image)
	}
	if gotPayload.Image.Caption != "TinkuBot" {
		t.Fatalf("unexpected image caption: %+v", gotPayload.Image)
	}
}

func TestSendLocationRequestSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendLocationRequest(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"Comparte tu ubicación para continuar.",
	)
	if err != nil {
		t.Fatalf("SendLocationRequest returned error: %v", err)
	}

	if gotPayload.Type != "interactive" || gotPayload.Interactive == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Interactive.Type != "location_request_message" {
		t.Fatalf("expected location_request_message, got %+v", gotPayload.Interactive)
	}
	if gotPayload.Interactive.Action.Name != "send_location" {
		t.Fatalf("expected action send_location, got %+v", gotPayload.Interactive.Action)
	}
}

func TestSendFlowSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendFlow(
		context.Background(),
		"1022104724314763",
		"593998823053",
		"Completa tu registro inicial",
		webhook.UIConfig{
			Type:       "flow",
			FlowID:     "flow-onboarding-1",
			FlowCTA:    "Empezar",
			FlowMode:   "published",
			FlowAction: "navigate",
			FlowActionPayload: map[string]any{
				"screen": "CONSENT_CITY",
			},
		},
	)
	if err != nil {
		t.Fatalf("SendFlow returned error: %v", err)
	}

	if gotPayload.Type != "interactive" || gotPayload.Interactive == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Interactive.Type != "flow" {
		t.Fatalf("expected flow interactive type, got %+v", gotPayload.Interactive)
	}
	if gotPayload.Interactive.Action.Name != "flow" {
		t.Fatalf("expected action name flow, got %+v", gotPayload.Interactive.Action)
	}
	if gotPayload.Interactive.Action.Parameters == nil {
		t.Fatalf("expected flow parameters, got nil")
	}
	if gotPayload.Interactive.Action.Parameters.FlowID != "flow-onboarding-1" {
		t.Fatalf("unexpected flow id: %+v", gotPayload.Interactive.Action.Parameters)
	}
}

func TestSendTemplateSuccess(t *testing.T) {
	var gotPayload sendMessagePayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		APIVersion:  "v22.0",
		AccessToken: "token-123",
	})

	err := client.SendTemplate(
		context.Background(),
		"1022104724314763",
		"593998823053",
		webhook.UIConfig{
			Type:             "template",
			TemplateName:     "tinkubot_onboarding_precontractual_v1",
			TemplateLanguage: "es",
			TemplateComponents: []map[string]any{
				{
					"type": "header",
					"parameters": []any{
						map[string]any{
							"type": "image",
							"image": map[string]any{
								"link": "https://example.com/logo.png",
							},
						},
					},
				},
				{
					"type":     "button",
					"sub_type": "quick_reply",
					"index":    "0",
					"parameters": []any{
						map[string]any{
							"type":    "payload",
							"payload": "continue_onboarding",
						},
					},
				},
			},
		},
	)
	if err != nil {
		t.Fatalf("SendTemplate returned error: %v", err)
	}

	if gotPayload.Type != "template" || gotPayload.Template == nil {
		t.Fatalf("unexpected payload type: %+v", gotPayload)
	}
	if gotPayload.Template.Name != "tinkubot_onboarding_precontractual_v1" {
		t.Fatalf("unexpected template name: %+v", gotPayload.Template)
	}
	if gotPayload.Template.Language.Code != "es" {
		t.Fatalf("unexpected template language: %+v", gotPayload.Template)
	}
	if len(gotPayload.Template.Components) != 2 {
		t.Fatalf("expected 2 template components, got %d", len(gotPayload.Template.Components))
	}
	buttonComponent := gotPayload.Template.Components[1]
	if buttonComponent.Type != "button" || buttonComponent.SubType != "quick_reply" || buttonComponent.Index != "0" {
		t.Fatalf("unexpected template button component: %+v", buttonComponent)
	}
	if len(buttonComponent.Parameters) != 1 || buttonComponent.Parameters[0]["payload"] != "continue_onboarding" {
		t.Fatalf("unexpected template button parameters: %+v", buttonComponent.Parameters)
	}
}

func TestSendTextRetriesServerErrors(t *testing.T) {
	attempts := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte(`{"error":"gateway"}`))
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:       srv.URL,
		APIVersion:    "v22.0",
		AccessToken:   "token-123",
		RetryAttempts: 2,
	})

	err := client.SendText(context.Background(), "1022104724314763", "593998823053", "hola")
	if err == nil {
		t.Fatal("expected error for repeated 5xx")
	}
	if attempts != 3 {
		t.Fatalf("expected 3 attempts, got %d", attempts)
	}
}

func TestSendTextStopsOnClientErrors(t *testing.T) {
	attempts := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"error":"bad request"}`))
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:       srv.URL,
		APIVersion:    "v22.0",
		AccessToken:   "token-123",
		RetryAttempts: 3,
	})

	err := client.SendText(context.Background(), "1022104724314763", "593998823053", "hola")
	if err == nil {
		t.Fatal("expected error for 4xx")
	}
	if attempts != 1 {
		t.Fatalf("expected 1 attempt for 4xx, got %d", attempts)
	}
	if !strings.Contains(err.Error(), "status=400") {
		t.Fatalf("expected status in error, got %v", err)
	}
}
