package outbound

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"

	"github.com/tinkubot/wa-gateway/internal/webhook"
)

var (
	// ErrMetaNotConfigured indicates the account is configured to send via Meta
	// but required runtime dependencies/config are missing.
	ErrMetaNotConfigured = errors.New("meta outbound not configured")
)

// MetaSender sends messages through Meta Cloud API.
type MetaSender interface {
	SendText(ctx context.Context, phoneNumberID, to, body string) error
	SendButtons(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendList(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendLocationRequest(ctx context.Context, phoneNumberID, to, body string) error
	SendFlow(ctx context.Context, phoneNumberID, to, body string, ui webhook.UIConfig) error
	SendTemplate(ctx context.Context, phoneNumberID, to string, ui webhook.UIConfig) error
}

// RouterConfig controls outbound routing strategy.
type RouterConfig struct {
	MetaOutboundEnabled         bool
	MetaEnabledAccounts         map[string]bool
	AccountPhoneNumber          map[string]string
	MetaPreserveLIDForProviders bool
}

// Router routes outbound sends per account to the proper transport.
type Router struct {
	metaSender              MetaSender
	metaOutboundOn          bool
	metaEnabledAccount      map[string]bool
	accountPhoneNumber      map[string]string
	preserveLIDForProviders bool
}

// NewRouter builds a transport router.
func NewRouter(metaSender MetaSender, cfg RouterConfig) *Router {
	metaEnabled := cfg.MetaEnabledAccounts
	if metaEnabled == nil {
		metaEnabled = map[string]bool{}
	}
	accountPhoneNumber := cfg.AccountPhoneNumber
	if accountPhoneNumber == nil {
		accountPhoneNumber = map[string]string{}
	}

	return &Router{
		metaSender:              metaSender,
		metaOutboundOn:          cfg.MetaOutboundEnabled,
		metaEnabledAccount:      metaEnabled,
		accountPhoneNumber:      accountPhoneNumber,
		preserveLIDForProviders: cfg.MetaPreserveLIDForProviders,
	}
}

// SendText sends a text message through the configured transport for accountID.
func (r *Router) SendText(ctx context.Context, accountID, to, message string) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if !r.shouldUseMeta(accountID) {
		return fmt.Errorf("%w: account=%s", ErrMetaNotConfigured, accountID)
	}
	if r.metaSender == nil {
		return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
	}
	phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
	if phoneNumberID == "" {
		return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
	}
	metaTo := r.resolveMetaDestination(accountID, to)
	if metaTo == "" {
		return fmt.Errorf("invalid meta destination for account=%s", accountID)
	}
	return r.metaSender.SendText(ctx, phoneNumberID, metaTo, message)
}

// SendButtons sends buttons through Meta when available, or falls back to text.
func (r *Router) SendButtons(
	ctx context.Context,
	accountID, to, message string,
	ui webhook.UIConfig,
) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if r.shouldUseMeta(accountID) {
		if r.metaSender == nil {
			return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
		}
		phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
		if phoneNumberID == "" {
			return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
		}
		metaTo := r.resolveMetaDestination(accountID, to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendButtons(ctx, phoneNumberID, metaTo, message, ui)
	}

	return r.SendText(ctx, accountID, to, message)
}

// SendList sends a list through Meta when available, or falls back to text.
func (r *Router) SendList(
	ctx context.Context,
	accountID, to, message string,
	ui webhook.UIConfig,
) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if r.shouldUseMeta(accountID) {
		if r.metaSender == nil {
			return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
		}
		phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
		if phoneNumberID == "" {
			return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
		}
		metaTo := r.resolveMetaDestination(accountID, to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendList(ctx, phoneNumberID, metaTo, message, ui)
	}

	return r.SendText(ctx, accountID, to, message)
}

// SendLocationRequest sends a location request through Meta when available, or falls back to text.
func (r *Router) SendLocationRequest(
	ctx context.Context,
	accountID, to, message string,
) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if r.shouldUseMeta(accountID) {
		if r.metaSender == nil {
			return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
		}
		phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
		if phoneNumberID == "" {
			return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
		}
		metaTo := r.resolveMetaDestination(accountID, to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendLocationRequest(ctx, phoneNumberID, metaTo, message)
	}

	return r.SendText(ctx, accountID, to, message)
}

// SendFlow sends a flow through Meta when available, or falls back to text.
func (r *Router) SendFlow(
	ctx context.Context,
	accountID, to, message string,
	ui webhook.UIConfig,
) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if r.shouldUseMeta(accountID) {
		if r.metaSender == nil {
			return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
		}
		phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
		if phoneNumberID == "" {
			return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
		}
		metaTo := r.resolveMetaDestination(accountID, to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendFlow(ctx, phoneNumberID, metaTo, message, ui)
	}

	return r.SendText(ctx, accountID, to, message)
}

// SendTemplate sends a template through Meta when available, or falls back to text.
func (r *Router) SendTemplate(
	ctx context.Context,
	accountID, to, message string,
	ui webhook.UIConfig,
) error {
	if r == nil {
		return fmt.Errorf("outbound router is nil")
	}
	if r.shouldUseMeta(accountID) {
		if r.metaSender == nil {
			return fmt.Errorf("%w: sender unavailable for account=%s", ErrMetaNotConfigured, accountID)
		}
		phoneNumberID := strings.TrimSpace(r.accountPhoneNumber[accountID])
		if phoneNumberID == "" {
			return fmt.Errorf("%w: missing phone_number_id for account=%s", ErrMetaNotConfigured, accountID)
		}
		metaTo := r.resolveMetaDestination(accountID, to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendTemplate(ctx, phoneNumberID, metaTo, ui)
	}

	return r.SendText(ctx, accountID, to, message)
}

func (r *Router) shouldUseMeta(accountID string) bool {
	if !r.metaOutboundOn {
		return false
	}
	// If allow-list exists, it is authoritative.
	if len(r.metaEnabledAccount) > 0 {
		return r.metaEnabledAccount[accountID]
	}
	// Fallback behavior: any account with configured phone_number_id uses Meta.
	_, exists := r.accountPhoneNumber[accountID]
	return exists
}

func (r *Router) resolveMetaDestination(accountID, to string) string {
	preserveJID := accountID == "bot-proveedores" && r.preserveLIDForProviders
	metaTo, strategy := normalizeMetaDestination(to, preserveJID)
	log.Printf(
		"[MetaOutboundRouter] account=%s original_to=%s normalized_to=%s strategy=%s preserve_lid=%t",
		accountID,
		strings.TrimSpace(to),
		metaTo,
		strategy,
		preserveJID,
	)
	return metaTo
}

// normalizeMetaDestination converts JID or formatted phone into the Meta outbound destination.
func normalizeMetaDestination(to string, preserveJID bool) (string, string) {
	to = strings.TrimSpace(to)
	if to == "" {
		return "", "empty"
	}
	if preserveJID && strings.Contains(to, "@") {
		return to, "preserve_full_jid"
	}
	if idx := strings.Index(to, "@"); idx > 0 {
		to = to[:idx]
	}

	var b strings.Builder
	for _, r := range to {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	metaTo := b.String()
	if metaTo == "" {
		return "", "invalid"
	}
	return metaTo, "digits_only"
}
