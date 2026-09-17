package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSendMeasurementBatch(t *testing.T) {
	var raw map[string][]map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/measurements/batch" {
			t.Errorf("request = %s %s, want POST /api/measurements/batch", r.Method, r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
			t.Errorf("decode body: %v", err)
		}
		_, _ = w.Write([]byte(`{"results": [{"measurement_uuid": "a", "status": 201},
			{"measurement_uuid": "b", "status": 409, "type": "duplicate_measurement"}]}`))
	}))
	defer srv.Close()

	at := time.Date(2026, 9, 17, 9, 0, 0, 0, time.FixedZone("", 5*60*60))
	ping := 12.5
	results, err := New(srv.URL, "tok").SendMeasurementBatch(context.Background(), []Measurement{
		{MeasurementUUID: "a", MeasuredAt: at, ConnectionStatus: "online", PingMs: &ping, AgentVersion: "dev"},
		{MeasurementUUID: "b", MeasuredAt: at, ConnectionStatus: "offline", AgentVersion: "dev"},
	})
	if err != nil || len(results) != 2 || !results[0].Delivered() || !results[1].Delivered() {
		t.Fatalf("SendMeasurementBatch = %+v, %v; want 201 and 409, both delivered", results, err)
	}
	first := raw["items"][0]
	if first["measured_at"] != "2026-09-17T09:00:00+05:00" || first["ping_ms"] != 12.5 {
		t.Fatalf("item = %v, want measured_at with offset (ADR-014) and ping_ms", first)
	}
	if _, ok := raw["items"][1]["download_mbps"]; ok {
		t.Fatalf("offline item = %v, want no empty metrics", raw["items"][1])
	}
	if _, err := New(srv.URL, "tok").SendMeasurementBatch(context.Background(), make([]Measurement, MaxBatchSize+1)); err == nil {
		t.Fatal("batch of 101: want error")
	}
}

func TestSendMeasurementAnswers(t *testing.T) {
	status := http.StatusConflict
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if status == http.StatusTooManyRequests {
			w.Header().Set("Retry-After", "90")
		}
		w.WriteHeader(status)
	}))
	defer srv.Close()
	c := New(srv.URL, "tok")

	if err := c.SendMeasurement(context.Background(), Measurement{MeasurementUUID: "a"}); err != nil {
		t.Fatalf("SendMeasurement on 409 = %v, want nil: the server already has it", err)
	}
	status = http.StatusUnprocessableEntity
	if err := c.SendMeasurement(context.Background(), Measurement{}); !Invalid(err) {
		t.Fatalf("SendMeasurement on 422 = %v, want Invalid", err)
	}
	status = http.StatusTooManyRequests
	err := c.SendMeasurement(context.Background(), Measurement{})
	if Invalid(err) || RetryAfter(err) != 90*time.Second {
		t.Fatalf("SendMeasurement on 429 = %v (Retry-After %v), want a temporary error with 90s", err, RetryAfter(err))
	}
}

func TestBackoff(t *testing.T) {
	var b Backoff
	var got []string
	for range 9 {
		got = append(got, b.Next(nil).String())
	}
	want := "[30s 1m0s 2m0s 4m0s 8m0s 16m0s 32m0s 1h0m0s 1h0m0s]"
	if s := "[" + strings.Join(got, " ") + "]"; s != want {
		t.Fatalf("pauses %s, want %s", s, want)
	}

	b.Reset()
	if d := b.Next(&ProblemError{Status: 429, RetryAfter: 5 * time.Minute}); d != 5*time.Minute {
		t.Fatalf("pause with Retry-After 5m = %v, want 5m", d)
	}
	if d := b.Next(&ProblemError{Status: 429, RetryAfter: 10 * time.Second}); d != time.Minute {
		t.Fatalf("pause with a short Retry-After = %v, want the backoff 1m", d)
	}
}

func TestParseRetryAfter(t *testing.T) {
	now := time.Date(2026, 9, 17, 4, 0, 0, 0, time.UTC)
	cases := map[string]time.Duration{
		"":                              0,
		"120":                           2 * time.Minute,
		"-5":                            0,
		"soon":                          0,
		"99999999999":                   retryAfterMax,
		"Thu, 17 Sep 2026 04:01:30 GMT": 90 * time.Second,
		"Thu, 17 Sep 2026 03:00:00 GMT": 0,
	}
	for value, want := range cases {
		if got := parseRetryAfter(value, now); got != want {
			t.Errorf("parseRetryAfter(%q) = %v, want %v", value, got, want)
		}
	}
}
