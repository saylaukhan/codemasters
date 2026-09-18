package service

import (
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
	"github.com/saylaukhan/codemasters/agent/internal/secure"
)

// TestRunConfigRotatesTokenOnRequest: a configuration with
// token_rotation_required makes the agent exchange its token once, save the
// new one and carry only it afterwards; the old one is refused (T-36).
func TestRunConfigRotatesTokenOnRequest(t *testing.T) {
	dir := t.TempDir()
	var mu sync.Mutex
	current, rotations := "7.old", 0
	var configAuths []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		if r.Header.Get("Authorization") != "Device "+current {
			w.Header().Set("Content-Type", "application/problem+json")
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"type": "unauthorized", "status": 401}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/api/agent/token" {
			rotations++
			current = "7.new"
			_, _ = w.Write([]byte(`{"device_id": 7, "device_token": "7.new"}`))
			return
		}
		configAuths = append(configAuths, current)
		body := serverConfigJSON("08:30:00", "09:00:00")
		if current == "7.old" {
			body = strings.Replace(body, `"thresholds": {}`, `"thresholds": {}, "token_rotation_required": true`, 1)
		}
		w.Header().Set("ETag", `"`+current+`"`)
		_, _ = w.Write([]byte(body))
	}))
	defer srv.Close()

	client := api.New(srv.URL, "7.old")
	settings := &Settings{}
	logger, _ := testLogger()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go runConfig(ctx, client, dir, settings, func(api.AgentConfig, scheduler.Schedule) {}, logger)

	deadline := time.Now().Add(5 * time.Second)
	for {
		mu.Lock()
		done := len(configAuths) >= 2
		mu.Unlock()
		if done {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("после замены токена конфигурация не запрошена за 5 с")
		}
		time.Sleep(20 * time.Millisecond)
	}
	cancel()

	mu.Lock()
	defer mu.Unlock()
	if rotations != 1 || configAuths[0] != "7.old" || configAuths[1] != "7.new" {
		t.Fatalf("замен %d, токены запросов конфигурации %q; ожидалась одна замена и затем новый токен",
			rotations, configAuths)
	}
	if client.Token() != "7.new" {
		t.Fatalf("токен клиента = %q, ожидался 7.new", client.Token())
	}
	saved, err := secure.ReadSecret(filepath.Join(dir, tokenFileName))
	if err != nil || string(saved) != "7.new" {
		t.Fatalf("сохранённый токен = %q (%v), ожидался 7.new", saved, err)
	}
	if settings.Current().TokenRotationRequired {
		t.Fatal("флаг замены токена остался после получения новой конфигурации")
	}
}
