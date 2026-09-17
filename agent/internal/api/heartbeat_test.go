package api

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// almaty is the local offset of a school computer (ADR-014).
var almaty = time.FixedZone("Asia/Almaty", 5*60*60)

func TestSendHeartbeat(t *testing.T) {
	var got map[string]any
	var auth, method, path string
	status := http.StatusNoContent
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		method, path, auth = r.Method, r.URL.Path, r.Header.Get("Authorization")
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode body: %v", err)
		}
		w.WriteHeader(status)
	}))
	defer srv.Close()
	c := New(srv.URL, "tok")

	at := time.Date(2026, 9, 17, 9, 0, 0, 0, almaty)
	if err := c.SendHeartbeat(context.Background(), at); err != nil {
		t.Fatalf("SendHeartbeat on 204 = %v, want nil", err)
	}
	if method != http.MethodPost || path != "/api/devices/heartbeat" || auth != "Device tok" {
		t.Fatalf("request = %s %s (%q), want POST /api/devices/heartbeat with the device token", method, path, auth)
	}
	if got["sent_at"] != "2026-09-17T09:00:00+05:00" || got["agent_version"] == "" {
		t.Fatalf("body = %v, want sent_at with the offset (ADR-014) and agent_version", got)
	}

	// The server answered, even with an error: the line is up, so this is not an outage.
	status = http.StatusInternalServerError
	err := c.SendHeartbeat(context.Background(), at)
	var pe *ProblemError
	if !errors.As(err, &pe) || pe.Status != http.StatusInternalServerError {
		t.Fatalf("SendHeartbeat on 500 = %v, want *ProblemError with status 500", err)
	}
}

func TestSendOutage(t *testing.T) {
	var got map[string]any
	var path string
	status := http.StatusCreated
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path = r.URL.Path
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode body: %v", err)
		}
		if status == http.StatusConflict {
			w.Header().Set("Content-Type", "application/problem+json")
			w.WriteHeader(status)
			_, _ = w.Write([]byte(`{"type": "duplicate_outage", "status": 409}`))
			return
		}
		w.WriteHeader(status)
		_, _ = w.Write([]byte(`{"id": 7}`))
	}))
	defer srv.Close()
	c := New(srv.URL, "tok")

	started := time.Date(2026, 9, 17, 9, 0, 0, 0, almaty)
	ended := started.Add(25 * time.Minute)
	if err := c.SendOutage(context.Background(), started, ended); err != nil {
		t.Fatalf("SendOutage on 201 = %v, want nil", err)
	}
	if path != "/api/outages" {
		t.Fatalf("path = %q, want /api/outages", path)
	}
	if got["started_at"] != "2026-09-17T09:00:00+05:00" || got["ended_at"] != "2026-09-17T09:25:00+05:00" {
		t.Fatalf("body = %v, want started_at and ended_at with the offset (ADR-014)", got)
	}

	// The answer was lost after the server stored the outage: the agent sends it again.
	status = http.StatusConflict
	if err := c.SendOutage(context.Background(), started, ended); err != nil {
		t.Fatalf("SendOutage on 409 = %v, want nil: the server already has it", err)
	}

	srv.Close() // no connection: the outage stays in the queue
	if err := c.SendOutage(context.Background(), started, ended); err == nil {
		t.Fatal("SendOutage with the server down: want error")
	}
}
