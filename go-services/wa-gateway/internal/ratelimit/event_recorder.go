package ratelimit

import "context"

// Event represents a persisted rate-limit hit.
type Event struct {
	AccountID        string
	Destination      string
	Window           string
	MessagesLastHour int
	MessagesLast24H  int
	LimitPerHour     int
	LimitPer24H      int
	RetryAt          string
	MetadataJSON     string
}

// EventRecorder persists rate-limit hits.
type EventRecorder interface {
	Record(context.Context, Event) error
}
