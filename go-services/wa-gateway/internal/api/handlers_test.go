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

type fakeMetaSender struct {
	buttonCalls   int
	listCalls     int
	flowCalls     int
	templateCalls int
	locationCalls int
	lastBody      string
	lastUI        *webhook.UIConfig
}

type fakeEventRecorder struct {
	events []ratelimit.Event
}

func (f *fakeEventRecorder) Record(_ context.Context, event ratelimit.Event) error {
	f.events = append(f.events, event)
	return nil
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

func (f *fakeMetaSender) SendList(
	_ context.Context,
	_ string,
	_ string,
	body string,
	ui webhook.UIConfig,
) error {
	f.listCalls++
	f.lastBody = body
	copyUI := ui
	f.lastUI = &copyUI
	return nil
}

func (f *fakeMetaSender) SendLocationRequest(
	_ context.Context,
	_ string,
	_ string,
	body string,
) error {
	f.locationCalls++
	f.lastBody = body
	f.lastUI = nil
	return nil
}

func (f *fakeMetaSender) SendFlow(
	_ context.Context,
	_ string,
	_ string,
	body string,
	ui webhook.UIConfig,
) error {
	f.flowCalls++
	f.lastBody = body
	copyUI := ui
	f.lastUI = &copyUI
	return nil
}

func (f *fakeMetaSender) SendTemplate(
	_ context.Context,
	_ string,
	_ string,
	ui webhook.UIConfig,
) error {
	f.templateCalls++
	copyUI := ui
	f.lastUI = &copyUI
	return nil
}

func TestPostSendDispatchesButtonsWhenUIProvided(t *testing.T) {
	gin.SetMode(gin.TestMode)
	metaSender := &fakeMetaSender{}
	router := outbound.NewRouter(
		metaSender,
		outbound.RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{"bot-clientes": true},
			AccountPhoneNumber:  map[string]string{"bot-clientes": "12345"},
		},
	)
	handlers := NewHandlers(
		ratelimit.NewLimiter(ratelimit.Config{MaxPerHour: 20, MaxPer24h: 100}),
		nil,
		router,
		HandlerConfig{},
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
				{"id": "confirm_new_search_city", "title": "Cambiar ciudad"},
				{"id": "confirm_new_search_service", "title": "Nueva solicitud"},
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

func TestPostSendDispatchesListWhenUIProvided(t *testing.T) {
	gin.SetMode(gin.TestMode)
	metaSender := &fakeMetaSender{}
	router := outbound.NewRouter(
		metaSender,
		outbound.RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{"bot-clientes": true},
			AccountPhoneNumber:  map[string]string{"bot-clientes": "12345"},
		},
	)
	handlers := NewHandlers(
		ratelimit.NewLimiter(ratelimit.Config{MaxPerHour: 20, MaxPer24h: 100}),
		nil,
		router,
		HandlerConfig{},
	)

	rec := httptest.NewRecorder()
	_, ginRouter := gin.CreateTestContext(rec)
	ginRouter.POST("/send", handlers.PostSend)

	body := map[string]any{
		"account_id": "bot-clientes",
		"to":         "593999111222",
		"message":    "TinkuBot Proveedores\n\nElige la opción de interés.",
		"ui": map[string]any{
			"type":               "list",
			"id":                 "provider_main_menu_v1",
			"list_button_text":   "Ver menú",
			"list_section_title": "Menú del Proveedor",
			"options": []map[string]any{
				{"id": "provider_menu_info_personal", "title": "Información personal"},
				{"id": "provider_menu_info_profesional", "title": "Información profesional"},
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
	if metaSender.listCalls != 1 {
		t.Fatalf("expected 1 list send, got %d", metaSender.listCalls)
	}
	if metaSender.lastUI == nil || metaSender.lastUI.Type != "list" {
		t.Fatalf("expected list UI, got %+v", metaSender.lastUI)
	}
}

func TestPostSendRejectsUnsupportedUIType(t *testing.T) {
	gin.SetMode(gin.TestMode)
	metaSender := &fakeMetaSender{}
	router := outbound.NewRouter(
		metaSender,
		outbound.RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{"bot-clientes": true},
			AccountPhoneNumber:  map[string]string{"bot-clientes": "12345"},
		},
	)
	handlers := NewHandlers(
		ratelimit.NewLimiter(ratelimit.Config{MaxPerHour: 20, MaxPer24h: 100}),
		nil,
		router,
		HandlerConfig{},
	)

	rec := httptest.NewRecorder()
	_, ginRouter := gin.CreateTestContext(rec)
	ginRouter.POST("/send", handlers.PostSend)

	body := map[string]any{
		"account_id": "bot-clientes",
		"to":         "593999111222",
		"message":    "Hola",
		"ui": map[string]any{
			"type": "unsupported",
		},
	}
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal body: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/send", bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	ginRouter.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d body=%s", rec.Code, rec.Body.String())
	}
	if metaSender.buttonCalls != 0 || metaSender.listCalls != 0 {
		t.Fatalf("unexpected interactive dispatch: %+v", metaSender)
	}
}

func TestPostSendReturnsRateLimitDetailsAndRecordsEvent(t *testing.T) {
	gin.SetMode(gin.TestMode)
	metaSender := &fakeMetaSender{}
	recorder := &fakeEventRecorder{}
	router := outbound.NewRouter(
		metaSender,
		outbound.RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{"bot-clientes": true},
			AccountPhoneNumber:  map[string]string{"bot-clientes": "12345"},
		},
	)
	limiter := ratelimit.NewLimiter(ratelimit.Config{MaxPerHour: 1, MaxPer24h: 100})
	if err := limiter.Increment(context.Background(), "bot-clientes", "593999111222"); err != nil {
		t.Fatalf("seed limiter: %v", err)
	}
	handlers := NewHandlers(
		limiter,
		nil,
		router,
		HandlerConfig{
			EventRecorder: recorder,
		},
	)

	rec := httptest.NewRecorder()
	_, ginRouter := gin.CreateTestContext(rec)
	ginRouter.POST("/send", handlers.PostSend)

	body := map[string]any{
		"account_id": "bot-clientes",
		"to":         "593999111222",
		"message":    "Hola",
		"metadata": map[string]any{
			"source_service": "ai-clientes",
			"flow_type":      "feedback_scheduler",
			"task_type":      "request_hiring_feedback",
		},
	}
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal body: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/send", bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	ginRouter.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("expected status 429, got %d body=%s", rec.Code, rec.Body.String())
	}

	var payload map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if payload["window"] != "hourly" {
		t.Fatalf("expected hourly window, got %+v", payload)
	}
	if payload["account_id"] != "bot-clientes" || payload["destination"] != "593999111222" {
		t.Fatalf("unexpected account/destination payload: %+v", payload)
	}
	if len(recorder.events) != 1 {
		t.Fatalf("expected 1 recorded event, got %d", len(recorder.events))
	}
	if recorder.events[0].MetadataJSON == "" {
		t.Fatalf("expected metadata to be persisted, got empty")
	}
}
