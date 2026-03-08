package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

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
