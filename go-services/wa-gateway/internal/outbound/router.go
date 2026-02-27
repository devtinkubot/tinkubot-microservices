package outbound

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

var (
	// ErrMetaNotConfigured indicates the account is configured to send via Meta
	// but required runtime dependencies/config are missing.
	ErrMetaNotConfigured = errors.New("meta outbound not configured")
)

// WebSender sends messages through WhatsMeow/Web transport.
type WebSender interface {
	SendTextMessage(accountID string, to string, message string) error
}

// MetaSender sends messages through Meta Cloud API.
type MetaSender interface {
	SendText(ctx context.Context, phoneNumberID, to, body string) error
}

// RouterConfig controls outbound routing strategy.
type RouterConfig struct {
	MetaOutboundEnabled bool
	MetaEnabledAccounts map[string]bool
	AccountPhoneNumber  map[string]string
}

// Router routes outbound sends per account to the proper transport.
type Router struct {
	webSender          WebSender
	metaSender         MetaSender
	metaOutboundOn     bool
	metaEnabledAccount map[string]bool
	accountPhoneNumber map[string]string
}

// NewRouter builds a transport router.
func NewRouter(webSender WebSender, metaSender MetaSender, cfg RouterConfig) *Router {
	metaEnabled := cfg.MetaEnabledAccounts
	if metaEnabled == nil {
		metaEnabled = map[string]bool{}
	}
	accountPhoneNumber := cfg.AccountPhoneNumber
	if accountPhoneNumber == nil {
		accountPhoneNumber = map[string]string{}
	}

	return &Router{
		webSender:          webSender,
		metaSender:         metaSender,
		metaOutboundOn:     cfg.MetaOutboundEnabled,
		metaEnabledAccount: metaEnabled,
		accountPhoneNumber: accountPhoneNumber,
	}
}

// SendText sends a text message through the configured transport for accountID.
func (r *Router) SendText(ctx context.Context, accountID, to, message string) error {
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
		metaTo := normalizeMetaDestination(to)
		if metaTo == "" {
			return fmt.Errorf("invalid meta destination for account=%s", accountID)
		}
		return r.metaSender.SendText(ctx, phoneNumberID, metaTo, message)
	}

	if r.webSender == nil {
		return fmt.Errorf("web sender unavailable for account=%s", accountID)
	}
	return r.webSender.SendTextMessage(accountID, to, message)
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

// normalizeMetaDestination converts JID or formatted phone into plain digits.
func normalizeMetaDestination(to string) string {
	to = strings.TrimSpace(to)
	if to == "" {
		return ""
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
	return b.String()
}
