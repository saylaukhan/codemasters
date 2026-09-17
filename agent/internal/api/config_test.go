package api

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const configBody = `{
	"timezone": "Asia/Almaty",
	"schedule_slots": [{"start": "08:30:00", "end": "09:00:00"}, {"start": "11:00:00", "end": "11:30:00"},
		{"start": "13:30:00", "end": "14:00:00"}],
	"heartbeat_interval_s": 300,
	"config_refresh_interval_s": 900,
	"speedtest": {"librespeed_url": "https://speedtest.example.kz", "ndt7_url": "wss://ndt7.example.kz"},
	"thresholds": {"download_mbps": 10},
	"latest_version": "0.2.0"
}`

// TestGetConfigETag: the first answer carries the configuration and its ETag,
// the second one only 304 - the body is not transferred (T-13).
func TestGetConfigETag(t *testing.T) {
	const etag = `W/"cfg-7"`
	var requests int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != http.MethodGet || r.URL.Path != "/api/agent/config" {
			t.Errorf("request = %s %s, want GET /api/agent/config", r.Method, r.URL.Path)
		}
		if auth := r.Header.Get("Authorization"); auth != "Device tok-42" {
			t.Errorf("Authorization = %q, want the device token", auth)
		}
		w.Header().Set("ETag", etag)
		if r.Header.Get("If-None-Match") == etag {
			w.WriteHeader(http.StatusNotModified)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(configBody))
	}))
	defer srv.Close()

	c := New(srv.URL, "tok-42")
	cfg, got, notModified, err := c.GetConfig(context.Background(), "")
	if err != nil {
		t.Fatalf("GetConfig: %v", err)
	}
	if notModified || got != etag {
		t.Fatalf("first GetConfig = etag %q, not modified %v; want %q and false", got, notModified, etag)
	}
	if err := cfg.Validate(); err != nil {
		t.Fatalf("Validate: %v", err)
	}
	if cfg.Timezone != "Asia/Almaty" || len(cfg.ScheduleSlots) != 3 || cfg.ScheduleSlots[0].Start != "08:30:00" ||
		cfg.HeartbeatIntervalS != 300 || cfg.ConfigRefreshIntervalS != 900 ||
		cfg.Speedtest.LibreSpeedURL != "https://speedtest.example.kz" || cfg.Speedtest.NDT7URL != "wss://ndt7.example.kz" ||
		cfg.LatestVersion != "0.2.0" {
		t.Fatalf("GetConfig = %+v, want the configuration of the answer", cfg)
	}

	again, got, notModified, err := c.GetConfig(context.Background(), etag)
	if err != nil {
		t.Fatalf("GetConfig with If-None-Match: %v", err)
	}
	if !notModified || got != etag {
		t.Fatalf("second GetConfig = etag %q, not modified %v; want %q and true", got, notModified, etag)
	}
	if again.Timezone != "" || len(again.ScheduleSlots) != 0 {
		t.Fatalf("304 returned a configuration %+v, want none: the body is not transferred", again)
	}
	if requests != 2 {
		t.Fatalf("requests = %d, want 2", requests)
	}
}

func TestGetConfigProblem(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusNotImplemented)
		_, _ = w.Write([]byte(`{"type": "not_implemented", "title": "Не реализовано", "status": 501}`))
	}))
	defer srv.Close()

	_, _, _, err := New(srv.URL, "tok").GetConfig(context.Background(), "")
	var pe *ProblemError
	if !errors.As(err, &pe) || pe.Status != http.StatusNotImplemented || !pe.Temporary() {
		t.Fatalf("GetConfig error = %v, want a temporary 501 problem", err)
	}
}

func TestAgentConfigValidate(t *testing.T) {
	ok := AgentConfig{
		Timezone:               "Asia/Almaty",
		ScheduleSlots:          []ScheduleSlot{{Start: "08:30:00", End: "09:00:00"}},
		HeartbeatIntervalS:     300,
		ConfigRefreshIntervalS: 900,
		Speedtest:              SpeedtestServers{LibreSpeedURL: "https://speedtest.example.kz"},
	}
	if err := ok.Validate(); err != nil {
		t.Fatalf("Validate: %v", err)
	}
	cases := map[string]func(*AgentConfig){
		"пустой timezone": func(c *AgentConfig) { c.Timezone = "" },
		"без слотов":      func(c *AgentConfig) { c.ScheduleSlots = nil },
		"интервалы":       func(c *AgentConfig) { c.ConfigRefreshIntervalS = 0 },
		"librespeed_url":  func(c *AgentConfig) { c.Speedtest.LibreSpeedURL = "speedtest.example.kz" },
	}
	for want, spoil := range cases {
		t.Run(want, func(t *testing.T) {
			cfg := ok
			spoil(&cfg)
			err := cfg.Validate()
			if err == nil || !strings.Contains(err.Error(), want) {
				t.Fatalf("Validate = %v, want an error about %q", err, want)
			}
		})
	}
}
