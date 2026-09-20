package api

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const releaseBody = `{
	"version": "0.2.0",
	"channel": "pilot",
	"download_url": "/api/agent/releases/0.2.0/VKO-Agent.msi",
	"sha256": "3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855e",
	"released_at": "2026-09-17T09:00:00+05:00"
}`

// TestGetLatestRelease: the answer carries the version, the file and its hash;
// the request goes with the device token and asks for nothing else - the
// channel is known to the server from the binding (T-50, ADR-005).
func TestGetLatestRelease(t *testing.T) {
	var method, path, auth, query string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		method, path, auth, query = r.Method, r.URL.Path, r.Header.Get("Authorization"), r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(releaseBody))
	}))
	defer srv.Close()

	rel, err := New(srv.URL, "tok-42").GetLatestRelease(context.Background())
	if err != nil {
		t.Fatalf("GetLatestRelease: %v", err)
	}
	if method != http.MethodGet || path != "/api/agent/releases/latest" || auth != "Device tok-42" || query != "" {
		t.Fatalf("request = %s %s?%s (%q), want GET /api/agent/releases/latest with the device token and no query",
			method, path, query, auth)
	}
	if rel.Version != "0.2.0" || rel.Channel != "pilot" ||
		rel.DownloadURL != "/api/agent/releases/0.2.0/VKO-Agent.msi" ||
		rel.SHA256 != "3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855e" {
		t.Fatalf("GetLatestRelease = %+v, want the release of the answer", rel)
	}
	if want := time.Date(2026, 9, 17, 9, 0, 0, 0, almaty); !rel.ReleasedAt.Equal(want) {
		t.Fatalf("released_at = %s, want %s", rel.ReleasedAt, want)
	}
	if err := rel.Validate(); err != nil {
		t.Fatalf("Validate: %v", err)
	}
}

// TestGetLatestReleaseNotFound: an empty channel is not a failure - the agent
// keeps its version and does not retry with a growing backoff.
func TestGetLatestReleaseNotFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"type": "not_found", "title": "Релиз не найден", "status": 404}`))
	}))
	defer srv.Close()

	_, err := New(srv.URL, "tok").GetLatestRelease(context.Background())
	if !errors.Is(err, ErrNoRelease) {
		t.Fatalf("GetLatestRelease on 404 = %v, want ErrNoRelease", err)
	}
}

// TestGetLatestReleaseProblem: a server failure stays a *ProblemError, so the
// caller waits and repeats (api.Backoff).
func TestGetLatestReleaseProblem(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = w.Write([]byte(`{"type": "unavailable", "title": "Сервер занят", "status": 503}`))
	}))
	defer srv.Close()

	_, err := New(srv.URL, "tok").GetLatestRelease(context.Background())
	var pe *ProblemError
	if !errors.As(err, &pe) || pe.Status != http.StatusServiceUnavailable || !pe.Temporary() {
		t.Fatalf("GetLatestRelease error = %v, want a temporary 503 problem", err)
	}
	if errors.Is(err, ErrNoRelease) {
		t.Fatalf("GetLatestRelease on 503 = %v, want a failure, not ErrNoRelease", err)
	}
}

func TestReleaseValidate(t *testing.T) {
	ok := Release{
		Version:     "0.2.0",
		Channel:     "stable",
		DownloadURL: "https://monitor.example.kz/releases/VKO-Agent.msi",
		SHA256:      "3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855e",
	}
	if err := ok.Validate(); err != nil {
		t.Fatalf("Validate: %v", err)
	}
	cases := map[string]func(*Release){
		"пустая версия":       func(r *Release) { r.Version = "" },
		"пустой download_url": func(r *Release) { r.DownloadURL = "" },
		"sha256":              func(r *Release) { r.SHA256 = strings.ToUpper(r.SHA256) },
	}
	for want, spoil := range cases {
		t.Run(want, func(t *testing.T) {
			rel := ok
			spoil(&rel)
			err := rel.Validate()
			if err == nil || !strings.Contains(err.Error(), want) {
				t.Fatalf("Validate = %v, want an error about %q", err, want)
			}
		})
	}
}
