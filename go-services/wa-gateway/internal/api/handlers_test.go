package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/outbound"
	"github.com/tinkubot/wa-gateway/internal/ratelimit"
	"github.com/tinkubot/wa-gateway/internal/webhook"
)

type fakeWebSender struct{}

func (f *fakeWebSender) SendTextMessage(accountID string, to string, message string) error {
	return nil
}

type fakeMetaSender struct {
	buttonCalls int
	lastBody    string
	lastUI      *webhook.UIConfig
}

func (f *fakeMetaSender) SendText(_ context.Context, _ string, _ string, _ string) error {
	return nil
}

func (f *fakeMetaSender) SendButtons(
	_ context.Context,
	_ string,
	_ string,
	body string,
	ui webhook.UIConfig,
) error {
	f.buttonCalls++
	f.lastBody = body
	copyUI := ui
	f.lastUI = &copyUI
	return nil
}

func TestGetAccountsShowsMetaManagedProvider(t *testing.T) {
	gin.SetMode(gin.TestMode)
	handlers := NewHandlers(nil, nil, nil, nil, nil, HandlerConfig{
		MetaManagedAccounts: map[string]bool{
			"bot-proveedores": true,
		},
	})

	rec := httptest.NewRecorder()
	ctx, router := gin.CreateTestContext(rec)
	router.GET("/accounts", handlers.GetAccounts)

	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
	ctx.Request = req
	router.HandleContext(ctx)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	var accounts []Account
	if err := json.Unmarshal(rec.Body.Bytes(), &accounts); err != nil {
		t.Fatalf("unmarshal accounts: %v", err)
	}
	if len(accounts) != 2 {
		t.Fatalf("expected 2 accounts, got %d", len(accounts))
	}

	var provider Account
	for _, account := range accounts {
		if account.AccountID == "bot-proveedores" {
			provider = account
			break
		}
	}
	if provider.ConnectionStatus != "meta_managed" {
		t.Fatalf("expected meta_managed, got %s", provider.ConnectionStatus)
	}
	if provider.Transport != "meta" {
		t.Fatalf("expected transport meta, got %s", provider.Transport)
	}
}

func TestMetaManagedAccountOperationsReturnConflict(t *testing.T) {
	gin.SetMode(gin.TestMode)
	handlers := NewHandlers(nil, nil, nil, nil, nil, HandlerConfig{
		MetaManagedAccounts: map[string]bool{
			"bot-proveedores": true,
		},
	})

	tests := []struct {
		name    string
		method  string
		target  string
		handler gin.HandlerFunc
	}{
		{name: "qr", method: http.MethodGet, target: "/accounts/bot-proveedores/qr", handler: handlers.GetQR},
		{name: "login", method: http.MethodPost, target: "/accounts/bot-proveedores/login", handler: handlers.PostLogin},
		{name: "logout", method: http.MethodPost, target: "/accounts/bot-proveedores/logout", handler: handlers.PostLogout},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			ctx, router := gin.CreateTestContext(rec)
			switch tc.method {
			case http.MethodGet:
				router.GET("/accounts/:accountId/qr", tc.handler)
			default:
				router.POST("/accounts/:accountId/"+tc.name, tc.handler)
			}

			req := httptest.NewRequest(tc.method, tc.target, nil)
			ctx.Request = req
			router.HandleContext(ctx)

			if rec.Code != http.StatusConflict {
				t.Fatalf("expected status 409, got %d", rec.Code)
			}

			var body map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
				t.Fatalf("unmarshal body: %v", err)
			}
			if body["code"] != "ACCOUNT_MANAGED_BY_META" {
				t.Fatalf("unexpected code: %+v", body)
			}
		})
	}
}

func TestPostSendDispatchesButtonsWhenUIProvided(t *testing.T) {
	gin.SetMode(gin.TestMode)
	metaSender := &fakeMetaSender{}
	router := outbound.NewRouter(
		&fakeWebSender{},
		metaSender,
		outbound.RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{"bot-clientes": true},
			AccountPhoneNumber:  map[string]string{"bot-clientes": "12345"},
		},
	)
	handlers := NewHandlers(
		nil,
		ratelimit.NewLimiter(ratelimit.Config{MaxPerHour: 20, MaxPer24h: 100}),
		nil,
		nil,
		router,
		HandlerConfig{MetaManagedAccounts: map[string]bool{"bot-clientes": true}},
	)

	rec := httptest.NewRecorder()
	_, ginRouter := gin.CreateTestContext(rec)
	ginRouter.POST("/send", handlers.PostSend)

	body := map[string]any{
		"account_id": "bot-clientes",
		"to":         "593999111222",
		"message":    "¿Te ayudo con otra solicitud?",
		"ui": map[string]any{
			"type": "buttons",
			"options": []map[string]any{
				{"id": "confirm_new_search_city", "title": "Buscar en otra ciudad"},
				{"id": "confirm_new_search_service", "title": "Buscar otro servicio"},
				{"id": "confirm_new_search_exit", "title": "Salir"},
			},
		},
	}
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal body: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/send", bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	ginRouter.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d body=%s", rec.Code, rec.Body.String())
	}
	if metaSender.buttonCalls != 1 {
		t.Fatalf("expected 1 button send, got %d", metaSender.buttonCalls)
	}
	if metaSender.lastBody != "¿Te ayudo con otra solicitud?" {
		t.Fatalf("unexpected body: %q", metaSender.lastBody)
	}
	if metaSender.lastUI == nil || metaSender.lastUI.Type != "buttons" {
		t.Fatalf("expected buttons UI, got %+v", metaSender.lastUI)
	}
}
