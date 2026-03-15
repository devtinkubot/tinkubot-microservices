package ratelimit

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"
)

func TestSQLiteEventRecorderPersistsEvent(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "rate-limit.db")
	recorder, err := NewSQLiteEventRecorder(dbPath)
	if err != nil {
		t.Fatalf("NewSQLiteEventRecorder: %v", err)
	}

	err = recorder.Record(context.Background(), Event{
		AccountID:        "bot-clientes",
		Destination:      "593999111222",
		Window:           "hourly",
		MessagesLastHour: 20,
		MessagesLast24H:  45,
		LimitPerHour:     20,
		LimitPer24H:      100,
		RetryAt:          "2026-03-14T20:00:00Z",
		MetadataJSON:     `{"source_service":"ai-clientes","flow_type":"feedback_scheduler"}`,
	})
	if err != nil {
		t.Fatalf("Record: %v", err)
	}

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("sql.Open: %v", err)
	}
	defer db.Close()

	var count int
	err = db.QueryRow(`SELECT COUNT(*) FROM rate_limit_events WHERE destination = ?`, "593999111222").Scan(&count)
	if err != nil {
		t.Fatalf("QueryRow: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 rate_limit_events row, got %d", count)
	}
}
