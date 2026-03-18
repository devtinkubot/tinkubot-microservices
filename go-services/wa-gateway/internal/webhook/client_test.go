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

	wc := NewWebhookClient(clientesServer.URL, providersServer.URL, "/handle-whatsapp-message", 1000, 0)

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
