package ratelimit

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Config holds rate limiter configuration
type Config struct {
	MaxPerHour int
	MaxPer24h  int
}

// Limiter performs rate limiting using Postgres
type Limiter struct {
	db     *pgxpool.Pool
	config Config
}

// NewLimiter creates a new rate limiter
func NewLimiter(db *pgxpool.Pool, config Config) *Limiter {
	if config.MaxPerHour == 0 {
		config.MaxPerHour = 20
	}
	if config.MaxPer24h == 0 {
		config.MaxPer24h = 100
	}

	return &Limiter{
		db:     db,
		config: config,
	}
}

// Check checks if a message is allowed under rate limits
func (rl *Limiter) Check(ctx context.Context, accountID, destinationPhone string) (bool, error) {
	// Get current counters
	var countHour, count24h int
	var windowStart, window24hStart time.Time
	var isBlocked bool
	var blockedUntil *time.Time

	err := rl.db.QueryRow(ctx, `
		SELECT messages_last_hour, messages_last_24h,
		       window_start_timetz, window_24h_start_timetz,
		       is_blocked, blocked_until
		FROM wa_rate_limits
		WHERE account_id = $1 AND destination_phone = $2
	`, accountID, destinationPhone).Scan(
		&countHour, &count24h,
		&windowStart, &window24hStart,
		&isBlocked, &blockedUntil,
	)

	if err != nil {
		// No record exists, allow message
		return true, nil
	}

	now := time.Now()

	// Check if blocked
	if isBlocked && blockedUntil != nil && now.Before(*blockedUntil) {
		return false, fmt.Errorf("blocked until %s", blockedUntil.Format(time.RFC3339))
	}

	// Reset counters if windows have expired
	if now.Sub(windowStart) >= time.Hour {
		countHour = 0
	}
	if now.Sub(window24hStart) >= 24*time.Hour {
		count24h = 0
	}

	// Check limits
	if countHour >= rl.config.MaxPerHour {
		return false, fmt.Errorf("hourly limit exceeded: %d/%d", countHour, rl.config.MaxPerHour)
	}
	if count24h >= rl.config.MaxPer24h {
		return false, fmt.Errorf("daily limit exceeded: %d/%d", count24h, rl.config.MaxPer24h)
	}

	return true, nil
}

// Increment increments the rate limit counters
func (rl *Limiter) Increment(ctx context.Context, accountID, destinationPhone string) error {
	now := time.Now()
	windowStart := now.Truncate(time.Hour)
	window24hStart := now.Truncate(24 * time.Hour)

	// Upsert rate limit record
	query := `
		INSERT INTO wa_rate_limits
		(account_id, destination_phone, messages_last_hour, messages_last_24h,
		 window_start_timetz, window_24h_start_timetz)
		VALUES ($1, $2, 1, 1, $3, $4)
		ON CONFLICT (account_id, destination_phone) DO UPDATE SET
			messages_last_hour = CASE
				WHEN $3 > wa_rate_limits.window_start_timetz
					THEN 1
					ELSE wa_rate_limits.messages_last_hour + 1
			END,
			messages_last_24h = CASE
				WHEN $4 > wa_rate_limits.window_24h_start_timetz
					THEN 1
					ELSE wa_rate_limits.messages_last_24h + 1
			END,
			window_start_timetz = CASE
				WHEN $3 > wa_rate_limits.window_start_timetz
					THEN $3
					ELSE wa_rate_limits.window_start_timetz
			END,
			window_24h_start_timetz = CASE
				WHEN $4 > wa_rate_limits.window_24h_start_timetz
					THEN $4
					ELSE wa_rate_limits.window_24h_start_timetz
			END,
			updated_at = NOW()
	`

	_, err := rl.db.Exec(ctx, query,
		accountID, destinationPhone,
		windowStart, window24hStart,
	)

	return err
}

// Reset resets the rate limit for a specific destination
func (rl *Limiter) Reset(ctx context.Context, accountID, destinationPhone string) error {
	_, err := rl.db.Exec(ctx, `
		DELETE FROM wa_rate_limits
		WHERE account_id = $1 AND destination_phone = $2
	`, accountID, destinationPhone)
	return err
}
