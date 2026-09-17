package service

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
)

// serverConfigJSON is an answer of GET /api/agent/config with one slot; the
// refresh interval is a second, so a test does not wait for 15 minutes.
func serverConfigJSON(start, end string) string {
	return fmt.Sprintf(`{"timezone": "Asia/Almaty", "schedule_slots": [{"start": %q, "end": %q}],
		"heartbeat_interval_s": 300, "config_refresh_interval_s": 1,
		"speedtest": {"librespeed_url": "https://speedtest.example.kz"}, "thresholds": {}}`, start, end)
}

func waitSchedule(t *testing.T, applied <-chan scheduler.Schedule) scheduler.Schedule {
	t.Helper()
	select {
	case s := <-applied:
		return s
	case <-time.After(5 * time.Second):
		t.Fatal("конфигурация не применена за 5 с")
		return scheduler.Schedule{}
	}
}

// TestRunConfigAppliesChangeAndCaches: a schedule changed on the server is
// applied on the next refresh, the answer is cached with its ETag and the
// unchanged configuration afterwards comes back as 304 (T-13).
func TestRunConfigAppliesChangeAndCaches(t *testing.T) {
	dir := t.TempDir()
	var mu sync.Mutex
	var requests, notModified int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requests++
		n := requests
		mu.Unlock()

		etag, body := `"v1"`, serverConfigJSON("08:30:00", "09:00:00")
		if n > 1 {
			etag, body = `"v2"`, serverConfigJSON("14:00:00", "14:30:00")
		}
		w.Header().Set("ETag", etag)
		if r.Header.Get("If-None-Match") == etag {
			mu.Lock()
			notModified++
			mu.Unlock()
			w.WriteHeader(http.StatusNotModified)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
	defer srv.Close()

	applied := make(chan scheduler.Schedule, 4)
	settings := &Settings{}
	logger, _ := testLogger()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go runConfig(ctx, api.New(srv.URL, "tok"), dir, settings,
		func(_ api.AgentConfig, s scheduler.Schedule) { applied <- s }, logger)

	if first := waitSchedule(t, applied); first.Slots[0].Start != 8*time.Hour+30*time.Minute {
		t.Fatalf("первое расписание = %v, ожидался слот 08:30", first.Slots)
	}
	if second := waitSchedule(t, applied); second.Slots[0].Start != 14*time.Hour {
		t.Fatalf("второе расписание = %v, ожидался слот 14:00", second.Slots)
	}
	if cfg := settings.Current(); cfg.HeartbeatIntervalS != 300 || cfg.ConfigRefreshIntervalS != 1 {
		t.Fatalf("текущая конфигурация = %+v, ожидались интервалы 300 и 1 с", cfg)
	}

	cached, err := readAgentConfig(dir)
	if err != nil {
		t.Fatalf("кэш конфигурации: %v", err)
	}
	if cached.ETag != `"v2"` || cached.Config.ScheduleSlots[0].Start != "14:00:00" {
		t.Fatalf("кэш = %+v, ожидались ETag \"v2\" и слот 14:00:00", cached)
	}

	// The configuration no longer changes: the server answers 304 and the body
	// is not transferred.
	deadline := time.Now().Add(5 * time.Second)
	for {
		mu.Lock()
		n := notModified
		mu.Unlock()
		if n > 0 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("повторный запрос с If-None-Match не пришёл")
		}
		time.Sleep(50 * time.Millisecond)
	}
	select {
	case s := <-applied:
		t.Fatalf("расписание применено заново без изменений: %v", s.Slots)
	default:
	}
}

// TestRunConfigStartsFromCache: without a connection the agent works by the
// last known schedule and sends its ETag to the server (ADR-006).
func TestRunConfigStartsFromCache(t *testing.T) {
	dir := t.TempDir()
	cached := cachedConfig{ETag: `"v7"`, FetchedAt: time.Now(), Config: api.AgentConfig{
		Timezone:               "Asia/Almaty",
		ScheduleSlots:          []api.ScheduleSlot{{Start: "11:00:00", End: "11:30:00"}},
		HeartbeatIntervalS:     300,
		ConfigRefreshIntervalS: 900,
		Speedtest:              api.SpeedtestServers{LibreSpeedURL: "https://speedtest.example.kz"},
	}}
	if err := writeAgentConfig(dir, cached); err != nil {
		t.Fatalf("writeAgentConfig: %v", err)
	}

	sent := make(chan string, 4)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case sent <- r.Header.Get("If-None-Match"):
		default:
		}
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	applied := make(chan scheduler.Schedule, 4)
	settings := &Settings{}
	logger, _ := testLogger()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go runConfig(ctx, api.New(srv.URL, "tok"), dir, settings,
		func(_ api.AgentConfig, s scheduler.Schedule) { applied <- s }, logger)

	if s := waitSchedule(t, applied); s.Slots[0].Start != 11*time.Hour {
		t.Fatalf("расписание из кэша = %v, ожидался слот 11:00", s.Slots)
	}
	select {
	case etag := <-sent:
		if etag != `"v7"` {
			t.Fatalf("If-None-Match = %q, ожидался ETag из кэша", etag)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("запрос конфигурации не пришёл")
	}
	if settings.Current().Speedtest.LibreSpeedURL != "https://speedtest.example.kz" {
		t.Fatalf("адрес сервера замеров = %q, ожидался адрес из кэша", settings.Current().Speedtest.LibreSpeedURL)
	}
	// The server is down, so the cached configuration stays in force.
	select {
	case s := <-applied:
		t.Fatalf("расписание применено заново при недоступном сервере: %v", s.Slots)
	case <-time.After(200 * time.Millisecond):
	}
}

func TestAgentScheduleRejectsBadConfig(t *testing.T) {
	cfg := api.AgentConfig{
		Timezone:               "Asia/Almaty",
		ScheduleSlots:          []api.ScheduleSlot{{Start: "8.30", End: "09:00:00"}},
		HeartbeatIntervalS:     300,
		ConfigRefreshIntervalS: 900,
		Speedtest:              api.SpeedtestServers{LibreSpeedURL: "https://speedtest.example.kz"},
	}
	if _, err := agentSchedule(cfg); err == nil {
		t.Fatal("agentSchedule: ожидалась ошибка разбора времени слота")
	}
	cfg.ScheduleSlots[0].Start = "08:30:00"
	if _, err := agentSchedule(cfg); err != nil {
		t.Fatalf("agentSchedule: %v", err)
	}
}
