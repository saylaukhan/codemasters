package service

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/queue"
)

func TestHeartbeatRecordsAndSendsOutage(t *testing.T) {
	var beats int
	var got []api.Outage
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/devices/heartbeat":
			beats++
			w.WriteHeader(http.StatusNoContent)
		case "/api/outages":
			var o api.Outage
			_ = json.NewDecoder(r.Body).Decode(&o)
			got = append(got, o)
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"id": 1}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	// A URL nobody listens on: the heartbeat gets no answer, as with the cable out.
	dead := httptest.NewServer(http.NotFoundHandler())
	deadURL := dead.URL
	dead.Close()

	ctx := context.Background()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	q, err := queue.Open(filepath.Join(t.TempDir(), queue.FileName), logger)
	if err != nil {
		t.Fatalf("queue.Open: %v", err)
	}
	defer q.Close()

	at := time.Date(2026, 9, 17, 9, 0, 0, 0, time.FixedZone("Asia/Almaty", 5*60*60))
	client := api.New(srv.URL, "tok")
	wake := make(chan struct{}, 1)
	const interval = 5 * time.Minute
	h := &heartbeat{opts: HeartbeatOptions{
		Client:   client,
		Queue:    q,
		Interval: func() time.Duration { return interval },
		Wake:     wake,
		Logger:   logger,
		Now:      func() time.Time { return at },
	}}

	h.beat(ctx) // the line is up
	if beats != 1 {
		t.Fatalf("heartbeats = %d, want 1", beats)
	}

	client.BaseURL = deadURL // the cable is out
	at = at.Add(interval)
	started := at
	h.beat(ctx)
	o, open, err := q.CurrentOutage(ctx)
	if err != nil || !open || !o.StartedAt.Equal(started) {
		t.Fatalf("CurrentOutage = %+v, %v, %v; want an outage open since %v", o, open, err, started)
	}
	at = at.Add(interval)
	h.beat(ctx)
	if o, _, _ := q.CurrentOutage(ctx); !o.LastFailedAt.Equal(at) {
		t.Fatalf("last failed check = %v, want %v", o.LastFailedAt, at)
	}

	select {
	case <-wake:
		t.Fatal("the queue was woken while there is no connection")
	default:
	}

	client.BaseURL = srv.URL // the cable is back
	at = at.Add(interval)
	h.beat(ctx)
	if len(got) != 1 || !got[0].StartedAt.Equal(started) || got[0].EndedAt.Sub(got[0].StartedAt) != 2*interval {
		t.Fatalf("server got %+v, want one outage of %v from %v", got, 2*interval, started)
	}
	if _, open, _ := q.CurrentOutage(ctx); open {
		t.Fatal("the outage is over, but the queue still has it open")
	}
	if left, _ := q.PendingOutages(ctx); len(left) != 0 {
		t.Fatalf("pending outages = %d after 201, want 0", len(left))
	}
	select {
	case <-wake:
	default:
		t.Fatal("the restored connection did not wake the queue of measurements")
	}
}

// The queue of measurements keeps its own pause between attempts, up to an
// hour (ADR-006): only a connection that came back may cut it short, or the
// heartbeat interval would become the upper bound of the backoff.
func TestHeartbeatWakesQueueOnlyWhenConnectionIsBack(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/devices/heartbeat":
			w.WriteHeader(http.StatusNoContent)
		case "/api/outages":
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"id": 1}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	// A URL nobody listens on: the heartbeat gets no answer, as with the cable out.
	dead := httptest.NewServer(http.NotFoundHandler())
	deadURL := dead.URL
	dead.Close()

	ctx := context.Background()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	q, err := queue.Open(filepath.Join(t.TempDir(), queue.FileName), logger)
	if err != nil {
		t.Fatalf("queue.Open: %v", err)
	}
	defer q.Close()

	at := time.Date(2026, 9, 17, 9, 0, 0, 0, time.FixedZone("Asia/Almaty", 5*60*60))
	client := api.New(srv.URL, "tok")
	wake := make(chan struct{}, 1)
	const interval = 5 * time.Minute
	h := &heartbeat{opts: HeartbeatOptions{
		Client:   client,
		Queue:    q,
		Interval: func() time.Duration { return interval },
		Wake:     wake,
		Logger:   logger,
		Now:      func() time.Time { return at },
	}}

	// The line was up all along: the device may still be blocked in the admin
	// panel (ТЗ п. 16) and the queue waiting out its hour after a 403.
	for range 3 {
		h.beat(ctx)
		at = at.Add(interval)
		select {
		case <-wake:
			t.Fatal("a heartbeat over a line that never went down woke the queue")
		default:
		}
	}

	client.BaseURL = deadURL // the cable is out
	h.beat(ctx)
	at = at.Add(interval)

	client.BaseURL = srv.URL // the cable is back
	h.beat(ctx)
	at = at.Add(interval)
	select {
	case <-wake:
	default:
		t.Fatal("the restored connection did not wake the queue of measurements")
	}

	h.beat(ctx)
	select {
	case <-wake:
		t.Fatal("the queue was woken twice for one restored connection")
	default:
	}
}

func TestHeartbeatServerErrorIsNotAnOutage(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"type": "server_error", "status": 500}`))
	}))
	defer srv.Close()

	ctx := context.Background()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	q, err := queue.Open(filepath.Join(t.TempDir(), queue.FileName), logger)
	if err != nil {
		t.Fatalf("queue.Open: %v", err)
	}
	defer q.Close()

	h := &heartbeat{opts: HeartbeatOptions{
		Client:   api.New(srv.URL, "tok"),
		Queue:    q,
		Interval: func() time.Duration { return DefaultHeartbeatInterval },
		Logger:   logger,
		Now:      time.Now,
	}}
	h.beat(ctx)
	if _, open, _ := q.CurrentOutage(ctx); open {
		t.Fatal("the server answered 500: the line is up, so this is not an outage")
	}
}
