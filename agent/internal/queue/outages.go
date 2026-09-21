package queue

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// Outage is a period the agent spent without connection (ТЗ п. 2, T-12). It
// lives in the same SQLite file as the measurements, so an outage survives a
// restart of the service and a long absence of the network (ADR-006).
// EndedAt is zero while the outage goes on.
type Outage struct {
	StartedAt    time.Time
	EndedAt      time.Time
	LastFailedAt time.Time
}

// OutageSender delivers outages to the server; *api.Client is one.
type OutageSender interface {
	SendOutage(ctx context.Context, startedAt, endedAt time.Time) error
}

// OpenOutage records the start of an outage. Writing the same started_at
// again changes nothing: it is the idempotency key of POST /api/outages.
func (q *Queue) OpenOutage(ctx context.Context, startedAt time.Time) error {
	ms := startedAt.UnixMilli()
	_, err := q.db.ExecContext(ctx,
		`INSERT INTO outages (started_at, last_failed_at) VALUES (?, ?)
		 ON CONFLICT (started_at) DO NOTHING`, ms, ms)
	if err != nil {
		return fmt.Errorf("очередь: начало простоя: %w", err)
	}
	return q.pruneOutages(ctx)
}

// TouchOutage remembers the last failed check of the open outage: after a
// restart it tells an outage of the line from a computer that was switched off.
func (q *Queue) TouchOutage(ctx context.Context, at time.Time) error {
	_, err := q.db.ExecContext(ctx,
		`UPDATE outages SET last_failed_at = ? WHERE ended_at IS NULL AND last_failed_at < ?`,
		at.UnixMilli(), at.UnixMilli())
	if err != nil {
		return fmt.Errorf("очередь: продолжение простоя: %w", err)
	}
	return nil
}

// CloseOutage ends the outage that began at startedAt; from now on it waits to
// be sent. Only that one is closed: a row left open by a failed write must not
// be ended by the next outage, or the server gets a week-long one. An endedAt
// before the start is moved to the start: the server rejects the other order
// (OutageCreate).
func (q *Queue) CloseOutage(ctx context.Context, startedAt, endedAt time.Time) error {
	_, err := q.db.ExecContext(ctx,
		`UPDATE outages SET ended_at = max(started_at, ?) WHERE ended_at IS NULL AND started_at = ?`,
		endedAt.UnixMilli(), startedAt.UnixMilli())
	if err != nil {
		return fmt.Errorf("очередь: конец простоя: %w", err)
	}
	return nil
}

// CurrentOutage returns the outage that is going on now, if there is one: the
// service reads it on start to continue counting the same outage.
func (q *Queue) CurrentOutage(ctx context.Context) (Outage, bool, error) {
	var started, lastFailed int64
	err := q.db.QueryRowContext(ctx,
		`SELECT started_at, last_failed_at FROM outages WHERE ended_at IS NULL ORDER BY started_at LIMIT 1`).
		Scan(&started, &lastFailed)
	if errors.Is(err, sql.ErrNoRows) {
		return Outage{}, false, nil
	}
	if err != nil {
		return Outage{}, false, fmt.Errorf("очередь: открытый простой: %w", err)
	}
	return Outage{StartedAt: time.UnixMilli(started), LastFailedAt: time.UnixMilli(lastFailed)}, true, nil
}

// PendingOutages returns finished outages the server has not confirmed yet,
// oldest first; a rejected one is never sent again.
func (q *Queue) PendingOutages(ctx context.Context) ([]Outage, error) {
	rows, err := q.db.QueryContext(ctx,
		`SELECT started_at, ended_at, last_failed_at FROM outages
		 WHERE ended_at IS NOT NULL AND rejected IS NULL ORDER BY started_at`)
	if err != nil {
		return nil, fmt.Errorf("очередь: простои к отправке: %w", err)
	}
	defer rows.Close()

	var out []Outage
	for rows.Next() {
		var started, ended, lastFailed int64
		if err := rows.Scan(&started, &ended, &lastFailed); err != nil {
			return nil, err
		}
		out = append(out, Outage{
			StartedAt:    time.UnixMilli(started),
			EndedAt:      time.UnixMilli(ended),
			LastFailedAt: time.UnixMilli(lastFailed),
		})
	}
	return out, rows.Err()
}

// RemoveOutage deletes a delivered outage; started_at identifies it.
func (q *Queue) RemoveOutage(ctx context.Context, startedAt time.Time) error {
	_, err := q.db.ExecContext(ctx, `DELETE FROM outages WHERE started_at = ?`, startedAt.UnixMilli())
	if err != nil {
		return fmt.Errorf("очередь: удаление отправленного простоя: %w", err)
	}
	return nil
}

// FlushOutages sends finished outages oldest first and returns how many the
// server confirmed. A record is deleted only after 201 or 409 (ADR-006);
// sending stops at the first failure, the rest waits for the next attempt.
func (q *Queue) FlushOutages(ctx context.Context, s OutageSender) (sent int, err error) {
	items, err := q.PendingOutages(ctx)
	if err != nil {
		return 0, err
	}
	for _, o := range items {
		switch err := s.SendOutage(ctx, o.StartedAt, o.EndedAt); {
		case api.Invalid(err):
			// Repeating the same body will never succeed, so the record is marked
			// and stops blocking the rest; deleted it is not, the server neither
			// confirmed nor stored it.
			q.logger.Error("сервер отклонил простой как невалидный: запись больше не отправляется",
				"started_at", o.StartedAt, "ended_at", o.EndedAt, "err", err)
			if err := q.rejectOutage(ctx, o.StartedAt, err.Error()); err != nil {
				return sent, err
			}
		case err != nil:
			return sent, err
		default:
			if err := q.RemoveOutage(ctx, o.StartedAt); err != nil {
				return sent, err
			}
			sent++
		}
	}
	return sent, nil
}

// rejectOutage marks an outage the server will never accept: it stays in the
// file until the age limit drops it, but is not sent again.
func (q *Queue) rejectOutage(ctx context.Context, startedAt time.Time, reason string) error {
	_, err := q.db.ExecContext(ctx,
		`UPDATE outages SET rejected = ? WHERE started_at = ?`, reason, startedAt.UnixMilli())
	if err != nil {
		return fmt.Errorf("очередь: отклонённый простой: %w", err)
	}
	return nil
}

// pruneOutages drops sent-out outages older than the queue age limit: they
// would be refused as too old anyway (ADR-006).
func (q *Queue) pruneOutages(ctx context.Context) error {
	cutoff := q.now().Add(-q.MaxAge()).UnixMilli()
	res, err := q.db.ExecContext(ctx,
		`DELETE FROM outages WHERE ended_at IS NOT NULL AND ended_at < ?`, cutoff)
	if err != nil {
		return fmt.Errorf("очередь: удаление старых простоев: %w", err)
	}
	if n, _ := res.RowsAffected(); n > 0 {
		q.logger.Warn("очередь: старые простои удалены без отправки", "older_than_limit", n)
	}
	return nil
}
