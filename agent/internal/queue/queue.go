// Package queue keeps measurements in SQLite until the server confirms them
// (ТЗ п. 2; ADR-006). A measurement is written here first and sent afterwards;
// a record is deleted only after the server answered 201 or 409 for its
// measurement_uuid, so a lost connection or a restart loses nothing.
package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	// SQLite without CGO (plan.md §2): the agent is cross-compiled for Windows.
	_ "modernc.org/sqlite"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// Limits of the queue (ADR-006): older and extra records are dropped, oldest first.
const (
	MaxAge     = 30 * 24 * time.Hour
	MaxRecords = 10000
)

// FileName is the queue database inside the agent data directory.
const FileName = "queue.db"

// busyTimeout lets the service and a CLI command use the file at the same time.
const busyTimeout = 5 * time.Second

const schema = `
CREATE TABLE IF NOT EXISTS measurements (
	id               INTEGER PRIMARY KEY AUTOINCREMENT,
	measurement_uuid TEXT    NOT NULL UNIQUE,
	measured_at      INTEGER NOT NULL, -- unix milliseconds
	body             TEXT    NOT NULL, -- api.Measurement as JSON
	rejected         TEXT              -- why the server will never accept the record (422); NULL while it is sent
);
CREATE INDEX IF NOT EXISTS measurements_measured_at ON measurements (measured_at, id);

CREATE TABLE IF NOT EXISTS outages (
	id             INTEGER PRIMARY KEY AUTOINCREMENT,
	started_at     INTEGER NOT NULL UNIQUE, -- unix milliseconds; the idempotency key of POST /api/outages
	last_failed_at INTEGER NOT NULL,        -- the last failed check of an open outage
	ended_at       INTEGER                  -- NULL while the outage goes on
);
`

// Queue is the local measurement queue. It is safe for concurrent use.
type Queue struct {
	db         *sql.DB
	logger     *slog.Logger
	now        func() time.Time
	maxAge     time.Duration
	maxRecords int
}

// Open opens or creates the queue database at path.
func Open(path string, logger *slog.Logger) (*Queue, error) {
	if logger == nil {
		logger = slog.Default()
	}
	dsn := fmt.Sprintf("%s?_pragma=busy_timeout(%d)&_pragma=journal_mode(WAL)", path, busyTimeout.Milliseconds())
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("очередь %s: %w", path, err)
	}
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("очередь %s: %w", path, err)
	}
	return &Queue{db: db, logger: logger, now: time.Now, maxAge: MaxAge, maxRecords: MaxRecords}, nil
}

// Close closes the database.
func (q *Queue) Close() error {
	return q.db.Close()
}

// Add puts a measurement into the queue. Adding the same measurement_uuid
// again changes nothing.
func (q *Queue) Add(ctx context.Context, m api.Measurement) error {
	if m.MeasurementUUID == "" {
		return errors.New("очередь: замер без measurement_uuid")
	}
	body, err := json.Marshal(m)
	if err != nil {
		return err
	}
	_, err = q.db.ExecContext(ctx,
		`INSERT INTO measurements (measurement_uuid, measured_at, body) VALUES (?, ?, ?)
		 ON CONFLICT (measurement_uuid) DO NOTHING`,
		m.MeasurementUUID, m.MeasuredAt.UnixMilli(), string(body))
	if err != nil {
		return fmt.Errorf("очередь: запись замера: %w", err)
	}
	return q.prune(ctx)
}

// Pending returns how many records wait to be sent.
func (q *Queue) Pending(ctx context.Context) (int, error) {
	var n int
	err := q.db.QueryRowContext(ctx, `SELECT count(*) FROM measurements WHERE rejected IS NULL`).Scan(&n)
	return n, err
}

// prune applies the limits: records older than maxAge go first, then the
// oldest records above maxRecords. Dropping is logged: it is lost data.
func (q *Queue) prune(ctx context.Context) error {
	cutoff := q.now().Add(-q.maxAge).UnixMilli()
	old, err := q.db.ExecContext(ctx, `DELETE FROM measurements WHERE measured_at < ?`, cutoff)
	if err != nil {
		return fmt.Errorf("очередь: удаление старых записей: %w", err)
	}
	extra, err := q.db.ExecContext(ctx,
		`DELETE FROM measurements WHERE id IN (
			SELECT id FROM measurements ORDER BY measured_at, id
			LIMIT max(0, (SELECT count(*) FROM measurements) - ?))`, q.maxRecords)
	if err != nil {
		return fmt.Errorf("очередь: удаление лишних записей: %w", err)
	}
	byAge, _ := old.RowsAffected()
	byCount, _ := extra.RowsAffected()
	if byAge+byCount > 0 {
		q.logger.Warn("очередь переполнена: старые замеры удалены без отправки",
			"older_than_limit", byAge, "over_count_limit", byCount)
	}
	return nil
}

// record is a queued measurement.
type record struct {
	id int64
	m  api.Measurement
}

// next returns up to limit records to send, oldest first.
func (q *Queue) next(ctx context.Context, limit int) ([]record, error) {
	rows, err := q.db.QueryContext(ctx,
		`SELECT id, body FROM measurements WHERE rejected IS NULL ORDER BY measured_at, id LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []record
	var broken []int64
	for rows.Next() {
		var r record
		var body string
		if err := rows.Scan(&r.id, &body); err != nil {
			return nil, err
		}
		if err := json.Unmarshal([]byte(body), &r.m); err != nil {
			broken = append(broken, r.id)
			continue
		}
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	rows.Close()
	for _, id := range broken {
		if err := q.reject(ctx, id, "запись в очереди повреждена"); err != nil {
			return nil, err
		}
	}
	return out, nil
}

// remove deletes delivered records by measurement_uuid.
func (q *Queue) remove(ctx context.Context, uuids []string) (int, error) {
	if len(uuids) == 0 {
		return 0, nil
	}
	args := make([]any, len(uuids))
	for i, u := range uuids {
		args[i] = u
	}
	res, err := q.db.ExecContext(ctx,
		`DELETE FROM measurements WHERE measurement_uuid IN (?`+strings.Repeat(", ?", len(uuids)-1)+`)`, args...)
	if err != nil {
		return 0, fmt.Errorf("очередь: удаление отправленных записей: %w", err)
	}
	n, _ := res.RowsAffected()
	return int(n), nil
}

// reject marks a record the server will never accept: it stays in the file
// until the limits drop it, but is not sent again.
func (q *Queue) reject(ctx context.Context, id int64, reason string) error {
	_, err := q.db.ExecContext(ctx, `UPDATE measurements SET rejected = ? WHERE id = ?`, reason, id)
	return err
}
