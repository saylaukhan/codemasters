package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// fakeOutages answers like the backend: 201 for a new started_at, 409
// duplicate_outage for a known one (ADR-006).
type fakeOutages struct {
	mu      sync.Mutex
	seen    map[string]bool
	got     []api.Outage
	fail    bool
	invalid bool
}

func newFakeOutages(t *testing.T) (*fakeOutages, *api.Client) {
	f := &fakeOutages{seen: map[string]bool{}}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	return f, api.New(srv.URL, "tok")
}

func (f *fakeOutages) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if r.URL.Path != "/api/outages" {
		http.NotFound(w, r)
		return
	}
	var o api.Outage
	_ = json.NewDecoder(r.Body).Decode(&o)
	if f.fail {
		problem(w, http.StatusServiceUnavailable, "server_error")
		return
	}
	f.got = append(f.got, o)
	if f.invalid {
		problem(w, http.StatusUnprocessableEntity, "validation_error")
		return
	}
	key := o.StartedAt.Format(time.RFC3339)
	if f.seen[key] {
		problem(w, http.StatusConflict, "duplicate_outage")
		return
	}
	f.seen[key] = true
	w.WriteHeader(http.StatusCreated)
	_, _ = w.Write([]byte(`{"id": 1}`))
}

func TestOutageSurvivesRestartAndIsSentOnce(t *testing.T) {
	path := filepath.Join(t.TempDir(), FileName)
	q := openQueue(t, path)
	ctx := context.Background()
	f, client := newFakeOutages(t)

	// The cable is out: the start is written at once, every failed check moves the last one.
	if err := q.OpenOutage(ctx, t0); err != nil {
		t.Fatalf("OpenOutage: %v", err)
	}
	if err := q.OpenOutage(ctx, t0); err != nil { // the same start again: no second record
		t.Fatalf("OpenOutage twice: %v", err)
	}
	if err := q.TouchOutage(ctx, t0.Add(5*time.Minute)); err != nil {
		t.Fatalf("TouchOutage: %v", err)
	}

	// The service restarts while the connection is still down.
	q.Close()
	q = openQueue(t, path)
	o, ok, err := q.CurrentOutage(ctx)
	if err != nil || !ok || !o.StartedAt.Equal(t0) || !o.LastFailedAt.Equal(t0.Add(5*time.Minute)) {
		t.Fatalf("CurrentOutage = %+v, %v, %v; want the outage open since %v", o, ok, err, t0)
	}
	if n, err := q.PendingOutages(ctx); err != nil || len(n) != 0 {
		t.Fatalf("PendingOutages while the outage is open = %v, %v; want none", n, err)
	}

	if err := q.CloseOutage(ctx, t0, t0.Add(10*time.Minute)); err != nil {
		t.Fatalf("CloseOutage: %v", err)
	}
	if _, ok, _ := q.CurrentOutage(ctx); ok {
		t.Fatal("CurrentOutage after CloseOutage: want no open outage")
	}

	sent, err := q.FlushOutages(ctx, client)
	if err != nil || sent != 1 {
		t.Fatalf("FlushOutages = %d, %v; want 1 sent", sent, err)
	}
	if len(f.got) != 1 || !f.got[0].StartedAt.Equal(t0) || f.got[0].EndedAt.Sub(f.got[0].StartedAt) != 10*time.Minute {
		t.Fatalf("server got %+v, want one outage of 10 min from %v", f.got, t0)
	}
	if left, err := q.PendingOutages(ctx); err != nil || len(left) != 0 {
		t.Fatalf("pending after 201 = %v, %v; want none", left, err)
	}
}

func TestOutageStaysUntilServerConfirms(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	ctx := context.Background()
	f, client := newFakeOutages(t)
	f.fail = true

	if err := q.OpenOutage(ctx, t0); err != nil {
		t.Fatalf("OpenOutage: %v", err)
	}
	if err := q.CloseOutage(ctx, t0, t0.Add(time.Minute)); err != nil {
		t.Fatalf("CloseOutage: %v", err)
	}
	if sent, err := q.FlushOutages(ctx, client); err == nil || sent != 0 {
		t.Fatalf("FlushOutages on 503 = %d, %v; want an error and nothing sent", sent, err)
	}
	if left, _ := q.PendingOutages(ctx); len(left) != 1 {
		t.Fatalf("pending after a failure = %d, want the outage kept", len(left))
	}

	// The answer was lost after the server stored the outage: 409 also means delivered.
	f.fail = false
	f.seen[t0.Format(time.RFC3339)] = true
	if sent, err := q.FlushOutages(ctx, client); err != nil || sent != 1 {
		t.Fatalf("FlushOutages on 409 = %d, %v; want 1 delivered", sent, err)
	}
	if left, _ := q.PendingOutages(ctx); len(left) != 0 {
		t.Fatalf("pending after 409 = %d, want 0", len(left))
	}
}

// outageRow reads a row straight from the file: the queue has no reader for a
// rejected outage, and the test must see the record is still there.
func outageRow(t *testing.T, q *Queue, startedAt time.Time) (int, string) {
	t.Helper()
	var n int
	var reason sql.NullString
	err := q.db.QueryRow(`SELECT count(*), max(rejected) FROM outages WHERE started_at = ?`,
		startedAt.UnixMilli()).Scan(&n, &reason)
	if err != nil {
		t.Fatalf("outageRow: %v", err)
	}
	return n, reason.String
}

func TestOutageRejectedAsInvalidStaysInTheFile(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	ctx := context.Background()
	f, client := newFakeOutages(t)
	f.invalid = true

	if err := q.OpenOutage(ctx, t0); err != nil {
		t.Fatalf("OpenOutage: %v", err)
	}
	if err := q.CloseOutage(ctx, t0, t0.Add(time.Minute)); err != nil {
		t.Fatalf("CloseOutage: %v", err)
	}
	if sent, err := q.FlushOutages(ctx, client); err != nil || sent != 0 {
		t.Fatalf("FlushOutages on 422 = %d, %v; want nothing sent and no error", sent, err)
	}

	// A record is deleted only after 201 or 409 (ADR-006): 422 marks it instead.
	if n, reason := outageRow(t, q, t0); n != 1 || reason == "" {
		t.Fatalf("outage after 422: rows = %d, rejected = %q; want the row kept and marked", n, reason)
	}
	if left, err := q.PendingOutages(ctx); err != nil || len(left) != 0 {
		t.Fatalf("pending after 422 = %v, %v; want none: the record is not sent again", left, err)
	}
	f.invalid = false
	if sent, err := q.FlushOutages(ctx, client); err != nil || sent != 0 {
		t.Fatalf("FlushOutages after 422 = %d, %v; want nothing sent", sent, err)
	}
	if len(f.got) != 1 {
		t.Fatalf("server got %d outages, want the rejected one tried once", len(f.got))
	}
}

func TestCloseOutageEndsOnlyTheOutageItWasGiven(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	ctx := context.Background()

	// The first outage stayed open: its end was never written (a disk error),
	// and the tracker has long forgotten it.
	stale := t0.Add(-7 * 24 * time.Hour)
	if err := q.OpenOutage(ctx, stale); err != nil {
		t.Fatalf("OpenOutage: %v", err)
	}
	if err := q.OpenOutage(ctx, t0); err != nil {
		t.Fatalf("OpenOutage: %v", err)
	}
	if err := q.CloseOutage(ctx, t0, t0.Add(10*time.Minute)); err != nil {
		t.Fatalf("CloseOutage: %v", err)
	}

	left, err := q.PendingOutages(ctx)
	if err != nil || len(left) != 1 || !left[0].StartedAt.Equal(t0) ||
		left[0].EndedAt.Sub(left[0].StartedAt) != 10*time.Minute {
		t.Fatalf("pending = %+v, %v; want only the outage of 10 min from %v", left, err, t0)
	}
	o, open, err := q.CurrentOutage(ctx)
	if err != nil || !open || !o.StartedAt.Equal(stale) {
		t.Fatalf("CurrentOutage = %+v, %v, %v; want the stale outage still open", o, open, err)
	}
}

func TestOpenKeepsOutagesOfAFileWithoutRejected(t *testing.T) {
	path := filepath.Join(t.TempDir(), FileName)
	// The table as an earlier agent wrote it, before the column appeared.
	old, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatalf("sql.Open: %v", err)
	}
	if _, err := old.Exec(`CREATE TABLE outages (
		id             INTEGER PRIMARY KEY AUTOINCREMENT,
		started_at     INTEGER NOT NULL UNIQUE,
		last_failed_at INTEGER NOT NULL,
		ended_at       INTEGER
	)`); err != nil {
		t.Fatalf("старая схема: %v", err)
	}
	if _, err := old.Exec(`INSERT INTO outages (started_at, last_failed_at, ended_at) VALUES (?, ?, ?)`,
		t0.UnixMilli(), t0.UnixMilli(), t0.Add(time.Minute).UnixMilli()); err != nil {
		t.Fatalf("старая запись: %v", err)
	}
	if err := old.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	q := openQueue(t, path)
	ctx := context.Background()
	left, err := q.PendingOutages(ctx)
	if err != nil || len(left) != 1 || !left[0].StartedAt.Equal(t0) {
		t.Fatalf("pending from an older file = %+v, %v; want the outage kept", left, err)
	}
	f, client := newFakeOutages(t)
	f.invalid = true
	if sent, err := q.FlushOutages(ctx, client); err != nil || sent != 0 {
		t.Fatalf("FlushOutages on 422 = %d, %v; want nothing sent and no error", sent, err)
	}
	if n, reason := outageRow(t, q, t0); n != 1 || reason == "" {
		t.Fatalf("outage of an older file after 422: rows = %d, rejected = %q; want it kept and marked", n, reason)
	}
}
