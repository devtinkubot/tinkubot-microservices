package webhook

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSendRoutesBotProveedoresToProvidersURL(t *testing.T) {
	var gotPayload WebhookPayload
	providersServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/handle-whatsapp-message" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		if r.Header.Get("X-Account-ID") != "bot-proveedores" {
			t.Fatalf("unexpected X-Account-ID: %s", r.Header.Get("X-Account-ID"))
		}
		if got := r.Header.Get("x-internal-token"); got != "" {
			t.Fatalf("unexpected x-internal-token on providers request: %q", got)
		}
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode payload: %v", err)
		}
		_ = json.NewEncoder(w).Encode(WebhookResponse{Success: true})
	}))
	defer providersServer.Close()

	clientesServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatalf("clientes server should not receive request: %s", r.URL.Path)
	}))
	defer clientesServer.Close()

	wc := NewWebhookClient(clientesServer.URL, providersServer.URL, "", "", "", "/handle-whatsapp-message", 1000, 0)

	resp, err := wc.Send(context.Background(), &WebhookPayload{
		AccountID:      "bot-proveedores",
		Phone:          "593999111222",
		FromNumber:     "593999111222@s.whatsapp.net",
		MessageType:    "interactive_button_reply",
		SelectedOption: "availability_accept",
		Message:        "",
	})
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if !resp.Success {
		t.Fatalf("expected success response")
	}
	if gotPayload.AccountID != "bot-proveedores" {
		t.Fatalf("expected forwarded account bot-proveedores, got %s", gotPayload.AccountID)
	}
	if gotPayload.SelectedOption != "availability_accept" {
		t.Fatalf("expected forwarded selected_option availability_accept, got %s", gotPayload.SelectedOption)
	}
}

func TestSendRoutesRustOnboardingForTestNumbers(t *testing.T) {
	var gotPayload WebhookPayload
	rustServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/handle-whatsapp-message" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		if r.Header.Get("X-Account-ID") != "bot-proveedores" {
			t.Fatalf("unexpected X-Account-ID: %s", r.Header.Get("X-Account-ID"))
		}
		if got := r.Header.Get("x-internal-token"); got != "secret-token" {
			t.Fatalf("unexpected x-internal-token on rust request: %q", got)
		}
		if err := json.NewDecoder(r.Body).Decode(&gotPayload); err != nil {
			t.Fatalf("decode payload: %v", err)
		}
		_ = json.NewEncoder(w).Encode(WebhookResponse{Success: true})
	}))
	defer rustServer.Close()

	clientesServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatalf("clientes server should not receive request: %s", r.URL.Path)
	}))
	defer clientesServer.Close()

	providersServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatalf("providers server should not receive request: %s", r.URL.Path)
	}))
	defer providersServer.Close()

	wc := NewWebhookClient(clientesServer.URL, providersServer.URL, rustServer.URL, "+593959091325, +593999999999", "secret-token", "/handle-whatsapp-message", 1000, 0)

	resp, err := wc.Send(context.Background(), &WebhookPayload{
		AccountID:      "bot-proveedores",
		Phone:          "593959091325",
		FromNumber:     "593959091325@s.whatsapp.net",
		MessageType:    "text",
		SelectedOption: "",
		Message:        "Registro",
	})
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if !resp.Success {
		t.Fatalf("expected success response")
	}
	if gotPayload.AccountID != "bot-proveedores" {
		t.Fatalf("expected forwarded account bot-proveedores, got %s", gotPayload.AccountID)
	}
	if gotPayload.FromNumber != "+593959091325" {
		t.Fatalf("expected forwarded from_number +593959091325, got %s", gotPayload.FromNumber)
	}
}

func TestNormalizePhoneNumber(t *testing.T) {
	cases := map[string]string{
		"+593959091325":            "+593959091325",
		"593959091325":             "+593959091325",
		"593959091325@s.whatsapp.net": "+593959091325",
		"  +593959091325  ":        "+593959091325",
	}

	for input, expected := range cases {
		if got := normalizePhoneNumber(input); got != expected {
			t.Fatalf("normalizePhoneNumber(%q) = %q, want %q", input, got, expected)
		}
	}
}
