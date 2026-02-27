package metaoutbound

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
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
	if gotPayload.MessagingProduct != "whatsapp" || gotPayload.Type != "text" || gotPayload.To != "593998823053" || gotPayload.Text.Body != "hola" {
		t.Fatalf("unexpected payload: %+v", gotPayload)
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
