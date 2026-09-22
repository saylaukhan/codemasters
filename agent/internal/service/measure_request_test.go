package service

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
)

// runningScheduler starts a scheduler whose measurements go into the returned
// channel. The previous measurement is now, so no slot of today is due and
// only a request of the panel measures within the seconds a test takes.
func runningScheduler(t *testing.T) (*scheduler.Scheduler, <-chan scheduler.Run) {
	t.Helper()
	slot, err := scheduler.ParseSlot("08:30", "09:00")
	if err != nil {
		t.Fatalf("ParseSlot: %v", err)
	}
	sched, err := scheduler.NewSchedule("Asia/Almaty", []scheduler.Slot{slot})
	if err != nil {
		t.Fatalf("NewSchedule: %v", err)
	}
	runs := make(chan scheduler.Run, 4)
	s := scheduler.New(scheduler.Options{
		Schedule: sched,
		Seed:     "device-a",
		Last:     time.Now(),
		Logger:   slog.New(slog.NewTextHandler(io.Discard, nil)),
		Measure:  func(_ context.Context, run scheduler.Run) { runs <- run },
	})
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	go s.Run(ctx)
	return s, runs
}

func waitRun(t *testing.T, runs <-chan scheduler.Run, why string) scheduler.Run {
	t.Helper()
	select {
	case run := <-runs:
		return run
	case <-time.After(5 * time.Second):
		t.Fatalf("%s: замер не выполнен за 5 с", why)
		return scheduler.Run{}
	}
}

func noRun(t *testing.T, runs <-chan scheduler.Run, why string) {
	t.Helper()
	select {
	case run := <-runs:
		t.Fatalf("%s: лишний замер %+v", why, run)
	case <-time.After(300 * time.Millisecond):
	}
}

// TestMeasureRequestMeasuresOncePerRequest: the server repeats the moment of
// the request in every heartbeat until the measurement reaches it, so one
// press of the button in the panel must stay one measurement (T-79).
func TestMeasureRequestMeasuresOncePerRequest(t *testing.T) {
	dir := t.TempDir()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	state := &stateFile{dir: dir, logger: logger}
	requests := &measureRequests{state: state, logger: logger}
	requested := time.Now().Add(-time.Minute).UTC()

	// The configuration has not arrived yet, so there is nothing to measure in:
	// the request is not remembered and the next heartbeat brings it again.
	requests.handle(requested)
	if st, err := ReadState(dir); err == nil && st.LastMeasureRequestAt != nil {
		t.Fatalf("запрос запомнен без расписания: %v", st.LastMeasureRequestAt)
	}

	sched, runs := runningScheduler(t)
	requests.setScheduler(sched)

	requests.handle(requested)
	if run := waitRun(t, runs, "запрос из панели"); !run.Manual {
		t.Errorf("run = %+v, want Manual", run)
	}

	// The same request repeats until the measurement reaches the server.
	requests.handle(requested)
	requests.handle(requested.Add(-time.Hour)) // an answer that overtook the previous one
	noRun(t, runs, "повтор того же запроса")

	// A restart of the service reads the moment back and does not measure again.
	st, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if st.LastMeasureRequestAt == nil || !st.LastMeasureRequestAt.Equal(requested) {
		t.Fatalf("last_measure_request_at = %v, want %s", st.LastMeasureRequestAt, requested)
	}
	restarted := &measureRequests{state: state, last: lastMeasureRequestAt(st), logger: logger}
	restarted.setScheduler(sched)
	restarted.handle(requested)
	noRun(t, runs, "тот же запрос после перезапуска службы")

	// A new press of the button is a new moment and measures again.
	restarted.handle(requested.Add(time.Minute))
	if run := waitRun(t, runs, "новый запрос из панели"); !run.Manual {
		t.Errorf("run = %+v, want Manual", run)
	}
}
