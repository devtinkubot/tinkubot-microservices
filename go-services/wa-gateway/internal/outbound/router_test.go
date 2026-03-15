package outbound

import (
	"context"
	"testing"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

type fakeWebSender struct{}

func (f *fakeWebSender) SendTextMessage(accountID string, to string, message string) error {
	_, _, _ = accountID, to, message
	return nil
}

type fakeMetaSender struct {
	lastTo string
}

func (f *fakeMetaSender) SendText(ctx context.Context, phoneNumberID, to, body string) error {
	_, _, _ = ctx, phoneNumberID, body
	f.lastTo = to
	return nil
}

func (f *fakeMetaSender) SendButtons(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	_, _, _, _ = ctx, phoneNumberID, body, ui
	f.lastTo = to
	return nil
}

func (f *fakeMetaSender) SendList(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	_, _, _, _ = ctx, phoneNumberID, body, ui
	f.lastTo = to
	return nil
}

func (f *fakeMetaSender) SendLocationRequest(
	ctx context.Context,
	phoneNumberID, to, body string,
) error {
	_, _, _ = ctx, phoneNumberID, body
	f.lastTo = to
	return nil
}

func (f *fakeMetaSender) SendFlow(
	ctx context.Context,
	phoneNumberID, to, body string,
	ui webhook.UIConfig,
) error {
	_, _, _, _ = ctx, phoneNumberID, body, ui
	f.lastTo = to
	return nil
}

func (f *fakeMetaSender) SendTemplate(
	ctx context.Context,
	phoneNumberID, to string,
	ui webhook.UIConfig,
) error {
	_, _, _ = ctx, phoneNumberID, ui
	f.lastTo = to
	return nil
}

func TestNormalizeMetaDestinationDigitsOnly(t *testing.T) {
	got, strategy := normalizeMetaDestination("39101516509235@lid", false)
	if got != "39101516509235" {
		t.Fatalf("expected digits-only destination, got %q", got)
	}
	if strategy != "digits_only" {
		t.Fatalf("expected digits_only strategy, got %q", strategy)
	}
}

func TestNormalizeMetaDestinationPreservesLIDWhenEnabled(t *testing.T) {
	got, strategy := normalizeMetaDestination("39101516509235@lid", true)
	if got != "39101516509235@lid" {
		t.Fatalf("expected preserved lid destination, got %q", got)
	}
	if strategy != "preserve_full_jid" {
		t.Fatalf("expected preserve_full_jid strategy, got %q", strategy)
	}
}

func TestNormalizeMetaDestinationPreservesWhatsAppJIDWhenEnabled(t *testing.T) {
	got, strategy := normalizeMetaDestination("593995971989@s.whatsapp.net", true)
	if got != "593995971989@s.whatsapp.net" {
		t.Fatalf("expected preserved whatsapp jid destination, got %q", got)
	}
	if strategy != "preserve_full_jid" {
		t.Fatalf("expected preserve_full_jid strategy, got %q", strategy)
	}
}

func TestRouterSendButtonsPreservesLIDOnlyForBotProveedores(t *testing.T) {
	meta := &fakeMetaSender{}
	router := NewRouter(
		&fakeWebSender{},
		meta,
		RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{
				"bot-proveedores": true,
			},
			AccountPhoneNumber: map[string]string{
				"bot-proveedores": "991862760681396",
			},
			MetaPreserveLIDForProviders: true,
		},
	)

	err := router.SendButtons(
		context.Background(),
		"bot-proveedores",
		"39101516509235@lid",
		"prueba",
		webhook.UIConfig{Type: "buttons"},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}
	if meta.lastTo != "39101516509235@lid" {
		t.Fatalf("expected preserved lid destination, got %q", meta.lastTo)
	}
}

func TestRouterSendButtonsPreservesWhatsAppJIDForBotProveedores(t *testing.T) {
	meta := &fakeMetaSender{}
	router := NewRouter(
		&fakeWebSender{},
		meta,
		RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{
				"bot-proveedores": true,
			},
			AccountPhoneNumber: map[string]string{
				"bot-proveedores": "991862760681396",
			},
			MetaPreserveLIDForProviders: true,
		},
	)

	err := router.SendButtons(
		context.Background(),
		"bot-proveedores",
		"593995971989@s.whatsapp.net",
		"prueba",
		webhook.UIConfig{Type: "buttons"},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}
	if meta.lastTo != "593995971989@s.whatsapp.net" {
		t.Fatalf("expected preserved whatsapp jid destination, got %q", meta.lastTo)
	}
}

func TestRouterSendButtonsKeepsDigitsForOtherAccounts(t *testing.T) {
	meta := &fakeMetaSender{}
	router := NewRouter(
		&fakeWebSender{},
		meta,
		RouterConfig{
			MetaOutboundEnabled: true,
			MetaEnabledAccounts: map[string]bool{
				"bot-clientes": true,
			},
			AccountPhoneNumber: map[string]string{
				"bot-clientes": "1022104724314763",
			},
			MetaPreserveLIDForProviders: true,
		},
	)

	err := router.SendButtons(
		context.Background(),
		"bot-clientes",
		"39101516509235@lid",
		"prueba",
		webhook.UIConfig{Type: "buttons"},
	)
	if err != nil {
		t.Fatalf("SendButtons returned error: %v", err)
	}
	if meta.lastTo != "39101516509235" {
		t.Fatalf("expected digits-only destination for non-provider account, got %q", meta.lastTo)
	}
}
