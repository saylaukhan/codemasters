package queue

import (
	"context"
	"errors"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// idleInterval is how often Run looks into the queue without a signal: the
// heartbeat period (plan.md §4.2), so a restored connection is noticed.
const idleInterval = 5 * time.Minute

// Sender delivers measurements to the server; *api.Client is one.
type Sender interface {
	SendMeasurement(ctx context.Context, m api.Measurement) error
	SendMeasurementBatch(ctx context.Context, items []api.Measurement) ([]api.BatchResult, error)
}

// Flush sends the queue oldest first: a single record by POST /api/measurements,
// more in batches of api.MaxBatchSize. It stops at the first failure and
// returns how many records the server confirmed; unconfirmed records stay.
func (q *Queue) Flush(ctx context.Context, s Sender) (sent int, err error) {
	if err := q.prune(ctx); err != nil {
		return 0, err
	}
	for {
		batch, err := q.next(ctx, api.MaxBatchSize)
		if err != nil || len(batch) == 0 {
			return sent, err
		}
		n, err := q.send(ctx, s, batch)
		sent += n
		if err != nil {
			return sent, err
		}
	}
}

func (q *Queue) send(ctx context.Context, s Sender, batch []record) (int, error) {
	if len(batch) == 1 {
		return q.sendOne(ctx, s, batch[0])
	}

	items := make([]api.Measurement, len(batch))
	inBatch := make(map[string]bool, len(batch))
	for i, r := range batch {
		items[i] = r.m
		inBatch[r.m.MeasurementUUID] = true
	}
	results, err := s.SendMeasurementBatch(ctx, items)
	if api.Invalid(err) {
		// One invalid record rejects the whole batch: find it by sending one by one.
		q.logger.Warn("пакет замеров отклонён как невалидный, отправка по одному", "size", len(batch), "err", err)
		sent := 0
		for _, r := range batch {
			n, err := q.sendOne(ctx, s, r)
			sent += n
			if err != nil {
				return sent, err
			}
		}
		return sent, nil
	}
	if err != nil {
		return 0, err
	}

	var delivered []string
	for _, r := range results {
		if r.Delivered() && inBatch[r.MeasurementUUID] {
			delivered = append(delivered, r.MeasurementUUID)
		}
	}
	if len(delivered) == 0 {
		return 0, errors.New("сервер не подтвердил ни одной записи пакета")
	}
	return q.remove(ctx, delivered)
}

func (q *Queue) sendOne(ctx context.Context, s Sender, r record) (int, error) {
	err := s.SendMeasurement(ctx, r.m)
	if api.Invalid(err) {
		q.logger.Error("сервер отклонил замер как невалидный: запись больше не отправляется",
			"measurement_uuid", r.m.MeasurementUUID, "err", err)
		return 0, q.reject(ctx, r.id, err.Error())
	}
	if err != nil {
		return 0, err
	}
	return q.remove(ctx, []string{r.m.MeasurementUUID})
}

// Run sends the queue until ctx is done: at once, on every signal from wake
// (a new measurement, a restored connection) and every idleInterval. After a
// failure the next attempt waits api.Backoff (30 s → 1 h); a signal from wake
// retries at once, but never before the Retry-After of the server. onFlush,
// when set, gets the number of pending records after each attempt.
func (q *Queue) Run(ctx context.Context, s Sender, wake <-chan struct{}, onFlush func(pending int)) {
	var backoff api.Backoff
	var notBefore time.Time
	for {
		wait := idleInterval
		sent, err := q.Flush(ctx, s)
		if ctx.Err() != nil {
			return
		}
		if err != nil {
			wait = backoff.Next(err)
			notBefore = time.Now().Add(api.RetryAfter(err))
			q.logger.Warn("отправка очереди не удалась, повтор позже", "sent", sent, "err", err, "retry_in", wait)
		} else {
			backoff.Reset()
			notBefore = time.Time{}
			if sent > 0 {
				q.logger.Info("очередь отправлена", "sent", sent)
			}
		}
		if pending, err := q.Pending(ctx); err == nil && onFlush != nil {
			onFlush(pending)
		}

		timer := time.NewTimer(wait)
		for waiting := true; waiting; {
			select {
			case <-ctx.Done():
				timer.Stop()
				return
			case <-timer.C:
				waiting = false
			case <-wake:
				if d := time.Until(notBefore); d > 0 {
					timer.Reset(d)
				} else {
					timer.Stop()
					waiting = false
				}
			}
		}
	}
}
