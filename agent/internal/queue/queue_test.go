package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

var t0 = time.Date(2026, 9, 17, 9, 0, 0, 0, time.FixedZone("Asia/Almaty", 5*60*60))

func openQueue(t *testing.T, path string) *Queue {
	t.Helper()
	q, err := Open(path, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { q.Close() })
	q.now = func() time.Time { return t0 }
	return q
}

func measurement(i int, at time.Time) api.Measurement {
	return api.Measurement{
		MeasurementUUID:  fmt.Sprintf("00000000-0000-4000-8000-%012d", i),
		MeasuredAt:       at,
		ConnectionStatus: "online",
		AgentVersion:     "test",
	}
}

func addN(t *testing.T, q *Queue, n int) {
	t.Helper()
	for i := range n {
		if err := q.Add(context.Background(), measurement(i, t0.Add(time.Duration(i)*time.Minute))); err != nil {
			t.Fatalf("Add: %v", err)
		}
	}
}

func uuids(t *testing.T, q *Queue) []string {
	t.Helper()
	recs, err := q.next(context.Background(), MaxRecords)
	if err != nil {
		t.Fatalf("next: %v", err)
	}
	out := make([]string, len(recs))
	for i, r := range recs {
		out[i] = r.m.MeasurementUUID
	}
	return out
}

func pending(t *testing.T, q *Queue) int {
	t.Helper()
	n, err := q.Pending(context.Background())
	if err != nil {
		t.Fatalf("Pending: %v", err)
	}
	return n
}

// fakeServer answers like the backend (ADR-006): 201 for a new measurement_uuid,
// 409 for a known one; fail, when set, answers instead.
type fakeServer struct {
	mu      sync.Mutex
	seen    map[string]bool
	batches []int
	singles int
	fail    func(w http.ResponseWriter, r *http.Request, uuids []string) bool
}

func newFakeServer(t *testing.T) (*fakeServer, *api.Client) {
	f := &fakeServer{seen: map[string]bool{}}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	return f, api.New(srv.URL, "tok")
}

func (f *fakeServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var items []api.Measurement
	switch r.URL.Path {
	case "/api/measurements":
		var m api.Measurement
		_ = json.NewDecoder(r.Body).Decode(&m)
		items = []api.Measurement{m}
		f.singles++
	case "/api/measurements/batch":
		var body struct{ Items []api.Measurement }
		_ = json.NewDecoder(r.Body).Decode(&body)
		items = body.Items
		f.batches = append(f.batches, len(items))
	default:
		http.NotFound(w, r)
		return
	}
	ids := make([]string, len(items))
	for i, m := range items {
		ids[i] = m.MeasurementUUID
	}
	if f.fail != nil && f.fail(w, r, ids) {
		return
	}

	results := make([]api.BatchResult, len(ids))
	for i, id := range ids {
		results[i] = api.BatchResult{MeasurementUUID: id, Status: http.StatusCreated}
		if f.seen[id] {
			results[i] = api.BatchResult{MeasurementUUID: id, Status: http.StatusConflict, Type: "duplicate_measurement"}
		}
		f.seen[id] = true
	}
	if r.URL.Path == "/api/measurements" {
		if results[0].Status == http.StatusConflict {
			problem(w, http.StatusConflict, "duplicate_measurement")
			return
		}
		w.WriteHeader(http.StatusCreated)
		_, _ = fmt.Fprintf(w, `{"measurement_uuid": %q, "received_at": "2026-09-17T04:00:00Z"}`, ids[0])
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"results": results})
}

func problem(w http.ResponseWriter, status int, typ string) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_, _ = fmt.Fprintf(w, `{"type": %q, "status": %d}`, typ, status)
}

func TestLimitsDropOldestFirst(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	q.maxRecords = 3
	ctx := context.Background()
	// Added out of order: the limit goes by measured_at, not by insertion.
	for _, i := range []int{4, 1, 5, 2, 3} {
		if err := q.Add(ctx, measurement(i, t0.Add(-time.Duration(10-i)*time.Hour))); err != nil {
			t.Fatalf("Add: %v", err)
		}
	}
	want := []string{measurement(3, t0).MeasurementUUID, measurement(4, t0).MeasurementUUID, measurement(5, t0).MeasurementUUID}
	if got := uuids(t, q); fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("after count limit: %v, want the 3 newest %v", got, want)
	}

	q.maxRecords = MaxRecords
	if err := q.Add(ctx, measurement(9, t0.Add(-DefaultMaxAge-time.Minute))); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if err := q.Add(ctx, measurement(5, t0)); err != nil { // same uuid again: no second record
		t.Fatalf("Add duplicate: %v", err)
	}
	if got := uuids(t, q); fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("after age limit and duplicate add: %v, want %v", got, want)
	}
}

func TestFlushSendsBatchesOldestFirst(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	f, client := newFakeServer(t)
	addN(t, q, 150)

	sent, err := q.Flush(context.Background(), client)
	if err != nil || sent != 150 {
		t.Fatalf("Flush = %d, %v; want 150 sent", sent, err)
	}
	if fmt.Sprint(f.batches) != "[100 50]" || f.singles != 0 {
		t.Fatalf("batches %v, singles %d; want [100 50] and no singles", f.batches, f.singles)
	}
	if n := pending(t, q); n != 0 {
		t.Fatalf("pending = %d after delivery, want 0", n)
	}
}

func TestDuplicateIsDeletedFromQueue(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	f, client := newFakeServer(t)
	ctx := context.Background()
	addN(t, q, 1)
	if sent, err := q.Flush(ctx, client); err != nil || sent != 1 || f.singles != 1 {
		t.Fatalf("Flush = %d, %v (singles %d); want one POST /api/measurements", sent, err, f.singles)
	}

	// The answer was lost after the server stored it: the agent sends the same record again.
	addN(t, q, 1)
	sent, err := q.Flush(ctx, client)
	if err != nil || sent != 1 {
		t.Fatalf("Flush of a duplicate = %d, %v; want 409 counted as delivered", sent, err)
	}
	if n := pending(t, q); n != 0 {
		t.Fatalf("pending = %d after 409, want 0", n)
	}
}

func TestFailureKeepsRecords(t *testing.T) {
	path := filepath.Join(t.TempDir(), FileName)
	q := openQueue(t, path)
	ctx := context.Background()
	addN(t, q, 120)

	down := httptest.NewServer(http.NotFoundHandler())
	down.Close() // network error: nobody listens
	if _, err := q.Flush(ctx, api.New(down.URL, "tok")); err == nil {
		t.Fatal("Flush with the server down: want error")
	}
	if n := pending(t, q); n != 120 {
		t.Fatalf("pending = %d after a network error, want 120", n)
	}

	f, client := newFakeServer(t)
	f.fail = func(w http.ResponseWriter, _ *http.Request, _ []string) bool {
		w.Header().Set("Retry-After", "120")
		problem(w, http.StatusTooManyRequests, "rate_limited")
		return true
	}
	_, err := q.Flush(ctx, client)
	if got := api.RetryAfter(err); got != 2*time.Minute {
		t.Fatalf("Flush on 429: err %v, Retry-After %v; want 2m", err, got)
	}

	// The service restarts: the records are still in the file and go out once the server answers.
	q.Close()
	q = openQueue(t, path)
	f.fail = nil
	if sent, err := q.Flush(ctx, client); err != nil || sent != 120 {
		t.Fatalf("Flush after restart = %d, %v; want 120 sent", sent, err)
	}
}

func TestInvalidRecordDoesNotBlockQueue(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	f, client := newFakeServer(t)
	ctx := context.Background()
	addN(t, q, 3)
	bad := measurement(1, t0).MeasurementUUID
	f.fail = func(w http.ResponseWriter, _ *http.Request, ids []string) bool {
		for _, id := range ids {
			if id == bad {
				problem(w, http.StatusUnprocessableEntity, "validation_error")
				return true
			}
		}
		return false
	}

	sent, err := q.Flush(ctx, client)
	if err != nil || sent != 2 {
		t.Fatalf("Flush = %d, %v; want the 2 valid records sent", sent, err)
	}
	if fmt.Sprint(f.batches) != "[3]" || f.singles != 3 {
		t.Fatalf("batches %v, singles %d; want a rejected batch of 3, then 3 singles", f.batches, f.singles)
	}
	if n := pending(t, q); n != 0 {
		t.Fatalf("pending = %d, want 0: the invalid record is not sent again", n)
	}
	var kept int
	if err := q.db.QueryRow(`SELECT count(*) FROM measurements WHERE rejected IS NOT NULL`).Scan(&kept); err != nil || kept != 1 {
		t.Fatalf("rejected records = %d, %v; want 1 kept in the file", kept, err)
	}
}

// TestSetMaxAgeFromServerRetention: the age limit is queue_retention_days of
// the server, not a constant of the agent (ТЗ п. 11, п. 20; ADR-006). A wider
// retention keeps a record the default would have dropped, a narrower one
// drops it, and a value the server did not send leaves the fallback in place.
func TestSetMaxAgeFromServerRetention(t *testing.T) {
	q := openQueue(t, filepath.Join(t.TempDir(), FileName))
	ctx := context.Background()
	old := measurement(1, t0.Add(-60*24*time.Hour))

	if q.MaxAge() != DefaultMaxAge {
		t.Fatalf("до конфигурации MaxAge = %v, ожидался запасной %v", q.MaxAge(), DefaultMaxAge)
	}

	q.SetMaxAge(90 * 24 * time.Hour)
	if err := q.Add(ctx, old); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if got := uuids(t, q); len(got) != 1 {
		t.Fatalf("при сроке 90 сут. в очереди %v, ожидался замер 60-суточной давности", got)
	}

	// The server did not say: the limit in force stays the one it said before.
	q.SetMaxAge(0)
	if q.MaxAge() != 90*24*time.Hour {
		t.Fatalf("после нулевого срока MaxAge = %v, ожидались прежние 90 сут.", q.MaxAge())
	}

	q.SetMaxAge(7 * 24 * time.Hour)
	if err := q.Add(ctx, measurement(2, t0)); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if got := uuids(t, q); fmt.Sprint(got) != fmt.Sprint([]string{measurement(2, t0).MeasurementUUID}) {
		t.Fatalf("при сроке 7 сут. в очереди %v, ожидался только свежий замер", got)
	}
}
