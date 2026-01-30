package ratelimit

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Config holds rate limiter configuration
type Config struct {
	MaxPerHour int
	MaxPer24h  int
}

// RateLimitEntry tracks rate limit state for a destination
type RateLimitEntry struct {
	MessagesLastHour int
	MessagesLast24H  int
	LastMessageTime  time.Time
	HourWindowStart  time.Time
	DayWindowStart   time.Time
}

// Limiter performs rate limiting using in-memory storage
type Limiter struct {
	mu     sync.RWMutex
	store  map[string]*RateLimitEntry
	config Config
}

// NewLimiter creates a new rate limiter with in-memory storage
func NewLimiter(config Config) *Limiter {
	if config.MaxPerHour == 0 {
		config.MaxPerHour = 20
	}
	if config.MaxPer24h == 0 {
		config.MaxPer24h = 100
	}

	return &Limiter{
		store:  make(map[string]*RateLimitEntry),
		config: config,
	}
}

// getKey returns the composite key for rate limiting
func getKey(accountID, destinationPhone string) string {
	return accountID + ":" + destinationPhone
}

// Check checks if a message is allowed under rate limits
func (rl *Limiter) Check(ctx context.Context, accountID, destinationPhone string) (bool, time.Duration, error) {
	key := getKey(accountID, destinationPhone)

	rl.mu.Lock()
	defer rl.mu.Unlock()

	entry, exists := rl.store[key]
	now := time.Now()

	if !exists {
		// First message, allow it
		return true, 0, nil
	}

	// Reset hour window if needed
	if now.Sub(entry.HourWindowStart) >= time.Hour {
		entry.MessagesLastHour = 0
		entry.HourWindowStart = now
	}

	// Reset day window if needed
	if now.Sub(entry.DayWindowStart) >= 24*time.Hour {
		entry.MessagesLast24H = 0
		entry.DayWindowStart = now
	}

	// Check hourly limit
	if entry.MessagesLastHour >= rl.config.MaxPerHour {
		retryAfter := time.Hour - now.Sub(entry.HourWindowStart)
		return false, retryAfter, fmt.Errorf("hourly limit exceeded: %d/%d", entry.MessagesLastHour, rl.config.MaxPerHour)
	}

	// Check daily limit
	if entry.MessagesLast24H >= rl.config.MaxPer24h {
		retryAfter := (24 * time.Hour) - now.Sub(entry.DayWindowStart)
		return false, retryAfter, fmt.Errorf("daily limit exceeded: %d/%d", entry.MessagesLast24H, rl.config.MaxPer24h)
	}

	return true, 0, nil
}

// Increment increments the rate limit counters
func (rl *Limiter) Increment(ctx context.Context, accountID, destinationPhone string) error {
	key := getKey(accountID, destinationPhone)
	now := time.Now()

	rl.mu.Lock()
	defer rl.mu.Unlock()

	entry, exists := rl.store[key]
	if !exists {
		// Create new entry
		rl.store[key] = &RateLimitEntry{
			MessagesLastHour: 1,
			MessagesLast24H:  1,
			LastMessageTime:  now,
			HourWindowStart:  now,
			DayWindowStart:   now,
		}
		return nil
	}

	// Reset hour window if needed
	if now.Sub(entry.HourWindowStart) >= time.Hour {
		entry.MessagesLastHour = 0
		entry.HourWindowStart = now
	}

	// Reset day window if needed
	if now.Sub(entry.DayWindowStart) >= 24*time.Hour {
		entry.MessagesLast24H = 0
		entry.DayWindowStart = now
	}

	// Increment counters
	entry.MessagesLastHour++
	entry.MessagesLast24H++
	entry.LastMessageTime = now

	return nil
}

// Reset resets the rate limit for a specific destination
func (rl *Limiter) Reset(ctx context.Context, accountID, destinationPhone string) error {
	key := getKey(accountID, destinationPhone)

	rl.mu.Lock()
	defer rl.mu.Unlock()

	delete(rl.store, key)
	return nil
}
