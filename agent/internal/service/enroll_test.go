package service

import (
	"bytes"
	"context"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/secure"
)

// registerServer answers POST /api/devices/register with the given statuses in
// turn (the last one repeats) and counts the calls.
func registerServer(t *testing.T, statuses ...int) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := int(calls.Add(1))
		status := statuses[min(n, len(statuses))-1]
		if status == http.StatusCreated {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(status)
			_, _ = w.Write([]byte(`{"device_id": 7, "device_token": "secret-device-token"}`))
			return
		}
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(`{"type": "enrollment_code_expired", "title": "Код просрочен", "status": 400}`))
	}))
	t.Cleanup(srv.Close)
	return srv, &calls
}

func testLogger() (*slog.Logger, *bytes.Buffer) {
	var buf bytes.Buffer
	return slog.New(slog.NewTextHandler(&buf, nil)), &buf
}

func TestEnrollRegistersOnce(t *testing.T) {
	srv, calls := registerServer(t, http.StatusCreated)
	cfg := Config{ServerURL: srv.URL, EnrollCode: "VKO-7F3K-92QD", DataDir: t.TempDir()}
	logger, _ := testLogger()

	id, token, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger)
	if !ok || id.DeviceID != 7 || token != "secret-device-token" {
		t.Fatalf("enroll = %+v, %q, %v; want device 7 with token", id, token, ok)
	}
	stored, err := secure.ReadSecret(filepath.Join(cfg.DataDir, tokenFileName))
	if err != nil || string(stored) != token {
		t.Fatalf("stored token = %q, %v; want %q", stored, err, token)
	}
	raw, err := os.ReadFile(filepath.Join(cfg.DataDir, identityFileName))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), token) {
		t.Fatalf("%s contains the token: %s", identityFileName, raw)
	}

	again, token2, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger)
	if !ok || again.DeviceID != 7 || again.DeviceUID != id.DeviceUID || token2 != token {
		t.Fatalf("second enroll = %+v, %q, %v; want the same identity", again, token2, ok)
	}
	if n := calls.Load(); n != 1 {
		t.Fatalf("register calls = %d, want 1", n)
	}
}

func TestEnrollRejectedCodeDoesNotStop(t *testing.T) {
	srv, calls := registerServer(t, http.StatusBadRequest)
	cfg := Config{ServerURL: srv.URL, EnrollCode: "VKO-OLD", DataDir: t.TempDir()}
	logger, logs := testLogger()

	_, _, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger)
	if ok {
		t.Fatal("enroll with a rejected code = ok, want not enrolled")
	}
	if n := calls.Load(); n != 1 {
		t.Fatalf("register calls = %d, want 1 (a rejected code is not retried)", n)
	}
	if !strings.Contains(logs.String(), "enrollment_code_expired") {
		t.Fatalf("log does not mention the rejection: %s", logs)
	}
	if _, err := os.Stat(filepath.Join(cfg.DataDir, tokenFileName)); !os.IsNotExist(err) {
		t.Fatalf("token file exists after rejection: %v", err)
	}
}

func TestEnrollRetriesTemporaryFailure(t *testing.T) {
	first, maxDelay := enrollRetryFirst, enrollRetryMax
	enrollRetryFirst, enrollRetryMax = time.Millisecond, 2*time.Millisecond
	t.Cleanup(func() { enrollRetryFirst, enrollRetryMax = first, maxDelay })

	srv, calls := registerServer(t, http.StatusServiceUnavailable, http.StatusNotImplemented, http.StatusCreated)
	cfg := Config{ServerURL: srv.URL, EnrollCode: "VKO-7F3K-92QD", DataDir: t.TempDir()}
	logger, _ := testLogger()

	id, _, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger)
	if !ok || id.DeviceID != 7 {
		t.Fatalf("enroll = %+v, %v; want device 7 after retries", id, ok)
	}
	if n := calls.Load(); n != 3 {
		t.Fatalf("register calls = %d, want 3", n)
	}
}

func TestEnrollWithoutCode(t *testing.T) {
	t.Setenv(enrollCodeEnv, "")
	srv, calls := registerServer(t, http.StatusCreated)
	cfg := Config{ServerURL: srv.URL, DataDir: t.TempDir()}
	logger, _ := testLogger()

	if _, _, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger); ok {
		t.Fatal("enroll without a code = ok, want not enrolled")
	}
	if n := calls.Load(); n != 0 {
		t.Fatalf("register calls = %d, want 0", n)
	}
}

func TestEnrollCodeFromEnv(t *testing.T) {
	t.Setenv(enrollCodeEnv, "VKO-ENV")
	srv, _ := registerServer(t, http.StatusCreated)
	cfg := Config{ServerURL: srv.URL, DataDir: t.TempDir()}
	logger, _ := testLogger()

	if _, _, ok := enroll(context.Background(), cfg, api.New(srv.URL, ""), logger); !ok {
		t.Fatal("enroll with ENROLL_CODE = not ok, want enrolled")
	}
}
