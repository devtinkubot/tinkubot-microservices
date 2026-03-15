package ratelimit

import (
	"context"
	"database/sql"
	_ "github.com/mattn/go-sqlite3"
)

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

// SQLiteEventRecorder stores rate-limit hits in SQLite.
type SQLiteEventRecorder struct {
	db *sql.DB
}

// NewSQLiteEventRecorder creates the recorder and ensures the table exists.
func NewSQLiteEventRecorder(databasePath string) (*SQLiteEventRecorder, error) {
	db, err := sql.Open("sqlite3", databasePath)
	if err != nil {
		return nil, err
	}
	recorder := &SQLiteEventRecorder{db: db}
	if err := recorder.ensureSchema(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return recorder, nil
}

func (r *SQLiteEventRecorder) ensureSchema() error {
	_, err := r.db.Exec(`
		CREATE TABLE IF NOT EXISTS rate_limit_events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			account_id TEXT NOT NULL,
			destination TEXT NOT NULL,
			window_type TEXT NOT NULL,
			messages_last_hour INTEGER NOT NULL,
			messages_last_24h INTEGER NOT NULL,
			limit_per_hour INTEGER NOT NULL,
			limit_per_24h INTEGER NOT NULL,
			retry_at TEXT NOT NULL,
			metadata_json TEXT NOT NULL DEFAULT ''
		)
	`)
	return err
}

// Record persists a rate-limit hit.
func (r *SQLiteEventRecorder) Record(ctx context.Context, event Event) error {
	if r == nil || r.db == nil {
		return nil
	}
	_, err := r.db.ExecContext(
		ctx,
		`INSERT INTO rate_limit_events (
			account_id,
			destination,
			window_type,
			messages_last_hour,
			messages_last_24h,
			limit_per_hour,
			limit_per_24h,
			retry_at,
			metadata_json
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		event.AccountID,
		event.Destination,
		event.Window,
		event.MessagesLastHour,
		event.MessagesLast24H,
		event.LimitPerHour,
		event.LimitPer24H,
		event.RetryAt,
		event.MetadataJSON,
	)
	return err
}
