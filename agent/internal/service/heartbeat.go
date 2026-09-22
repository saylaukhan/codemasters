package service

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/queue"
	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
)

// DefaultHeartbeatInterval is how often the agent signals that it is alive
// while the server has not said otherwise (plan.md §4.2). The server sends
// the interval in GET /api/agent/config (T-13): it is not built into the
// agent any deeper than this default (ADR-004).
const DefaultHeartbeatInterval = 5 * time.Minute

// HeartbeatOptions configure StartHeartbeat.
type HeartbeatOptions struct {
	// Client sends the heartbeat and the finished outages; required.
	Client *api.Client
	// Queue keeps outages until the server confirms them; required.
	Queue *queue.Queue
	// Interval is asked before every heartbeat, so a new interval from the
	// server configuration applies without a restart; nil means the default.
	Interval func() time.Duration
	// Wake, when set, is signalled once the connection is back, so the queue
	// of measurements is resent at once and not after its own pause (ADR-006).
	Wake chan<- struct{}
	// OnSuccess, when set, gets the time of every heartbeat the server
	// accepted. The heartbeat carries buildinfo.Version, so an accepted one
	// means the server knows which version runs here: that is what confirms a
	// self-update (T-50).
	OnSuccess func(at time.Time)
	// OnMeasureRequest, when set, gets the moment of a measurement asked for
	// in the admin panel (T-79). The server repeats it in every answer until
	// the measurement reaches it, so the handler decides what is new.
	OnMeasureRequest func(requestedAt time.Time)
	Logger           *slog.Logger
	// Now is the clock, time.Now when nil; tests replace it.
	Now func() time.Time
}

// heartbeat is the running heartbeat loop.
type heartbeat struct {
	opts    HeartbeatOptions
	tracker scheduler.OutageTracker
}

// StartHeartbeat starts the heartbeat loop in the background and returns at
// once; the loop stops with ctx. A heartbeat that does not reach the server
// is the fact of a lost connection: the agent records the outage locally and
// sends it with started_at and ended_at once the connection is back
// (ТЗ п. 2, п. 18; ADR-006, ADR-007).
func StartHeartbeat(ctx context.Context, opts HeartbeatOptions) {
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if opts.Interval == nil {
		opts.Interval = func() time.Duration { return DefaultHeartbeatInterval }
	}
	go (&heartbeat{opts: opts}).run(ctx)
}

// interval is the period between heartbeats; a broken value falls back to the default.
func (h *heartbeat) interval() time.Duration {
	if d := h.opts.Interval(); d > 0 {
		return d
	}
	return DefaultHeartbeatInterval
}

// run continues the outage that was open when the service stopped and then
// sends a heartbeat every interval until ctx is done.
func (h *heartbeat) run(ctx context.Context) {
	if o, ok, err := h.opts.Queue.CurrentOutage(ctx); err != nil {
		h.opts.Logger.Warn("чтение открытого простоя", "err", err)
	} else if ok {
		h.tracker.Resume(o.StartedAt, o.LastFailedAt)
		h.opts.Logger.Warn("простой продолжается после запуска службы",
			"started_at", o.StartedAt, "last_failed_at", o.LastFailedAt)
	}
	for {
		h.beat(ctx)
		if ctx.Err() != nil {
			return
		}
		timer := time.NewTimer(h.interval())
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
	}
}

// beat sends one heartbeat and records what it says about the connection.
func (h *heartbeat) beat(ctx context.Context) {
	at := h.opts.Now()
	answer, err := h.opts.Client.SendHeartbeat(ctx, at)
	if ctx.Err() != nil {
		return
	}

	// Any answer of the server, even an error one, means the line is up: only
	// a missing answer (a network error or a timeout) is an outage.
	online := true
	var problem *api.ProblemError
	switch {
	case errors.As(err, &problem):
		h.opts.Logger.Warn("сервер ответил ошибкой на heartbeat", "err", err)
	case err != nil:
		online = false
		h.opts.Logger.Warn("heartbeat не дошёл: связи нет", "err", err)
	default:
		if h.opts.OnSuccess != nil {
			h.opts.OnSuccess(at)
		}
		if answer.MeasureRequestedAt != nil && h.opts.OnMeasureRequest != nil {
			h.opts.OnMeasureRequest(*answer.MeasureRequestedAt)
		}
	}

	h.tracker.Interval = h.interval()
	event := h.tracker.Observe(at, online)
	h.record(ctx, event, at)
	if !online {
		return
	}
	// Only a restored connection wakes the queue: a beat while the line was up
	// all along would cancel the growing pause between resend attempts and turn
	// the upper bound of the backoff into the heartbeat interval (ADR-006).
	if event.Closed {
		h.wake()
	}
	if sent, err := h.opts.Queue.FlushOutages(ctx, h.opts.Client); err != nil {
		h.opts.Logger.Warn("отправка простоев не удалась, повтор позже", "sent", sent, "err", err)
	} else if sent > 0 {
		h.opts.Logger.Info("простои отправлены", "sent", sent)
	}
}

// record writes what the check changed into the queue, so a restart or a long
// absence of the network loses neither the start nor the length of an outage.
func (h *heartbeat) record(ctx context.Context, event scheduler.OutageEvent, at time.Time) {
	var err error
	switch {
	case event.Opened:
		h.opts.Logger.Warn("нет связи: начало простоя", "started_at", event.StartedAt)
		err = h.opts.Queue.OpenOutage(ctx, event.StartedAt)
	case event.Ongoing:
		err = h.opts.Queue.TouchOutage(ctx, at)
	case event.Closed:
		h.opts.Logger.Info("связь восстановлена", "started_at", event.StartedAt,
			"ended_at", event.EndedAt, "duration", event.Duration())
		err = h.opts.Queue.CloseOutage(ctx, event.StartedAt, event.EndedAt)
	}
	if err != nil {
		h.opts.Logger.Error("запись простоя в очередь", "err", err)
	}
}

// wake asks the queue of measurements to resend now; a full channel already
// carries the same signal, so the send never blocks the loop.
func (h *heartbeat) wake() {
	if h.opts.Wake == nil {
		return
	}
	select {
	case h.opts.Wake <- struct{}{}:
	default:
	}
}
