package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
)

// agentConfigFileName caches the last good configuration of the server in
// DataDir: after a restart without a connection the agent keeps working by the
// schedule it knows (ADR-006).
const agentConfigFileName = "agent-config.json"

// cachedConfig is what lies in DataDir/agent-config.json.
type cachedConfig struct {
	// ETag is the version of the configuration; it goes back as If-None-Match.
	ETag      string          `json:"etag"`
	FetchedAt time.Time       `json:"fetched_at"`
	Config    api.AgentConfig `json:"config"`
}

// readAgentConfig reads the cached configuration. A missing file returns an
// error that satisfies errors.Is(err, os.ErrNotExist).
func readAgentConfig(dataDir string) (cachedConfig, error) {
	path := filepath.Join(dataDir, agentConfigFileName)
	data, err := os.ReadFile(path)
	if err != nil {
		return cachedConfig{}, err
	}
	var c cachedConfig
	if err := json.Unmarshal(data, &c); err != nil {
		return cachedConfig{}, fmt.Errorf("разбор %s: %w", path, err)
	}
	return c, nil
}

// writeAgentConfig replaces the cache atomically, like WriteState.
func writeAgentConfig(dataDir string, c cachedConfig) error {
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	path := filepath.Join(dataDir, agentConfigFileName)
	if err := os.WriteFile(path+".tmp", data, 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}

// Settings holds the configuration of the server the agent works by now. It is
// read from several goroutines: the measurement, the heartbeat (T-12).
type Settings struct {
	mu  sync.RWMutex
	cur api.AgentConfig
}

// Current returns the configuration in force; the zero value until the first
// one arrives from the cache or the server.
func (s *Settings) Current() api.AgentConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.cur
}

func (s *Settings) set(cfg api.AgentConfig) {
	s.mu.Lock()
	s.cur = cfg
	s.mu.Unlock()
}

// agentSchedule builds the measurement schedule from the configuration of the
// server: the slots and the time zone are never built into the agent (ADR-004).
func agentSchedule(cfg api.AgentConfig) (scheduler.Schedule, error) {
	if err := cfg.Validate(); err != nil {
		return scheduler.Schedule{}, err
	}
	slots := make([]scheduler.Slot, 0, len(cfg.ScheduleSlots))
	for _, s := range cfg.ScheduleSlots {
		slot, err := scheduler.ParseSlot(s.Start, s.End)
		if err != nil {
			return scheduler.Schedule{}, err
		}
		slots = append(slots, slot)
	}
	return scheduler.NewSchedule(cfg.Timezone, slots)
}

// sameConfig reports whether two configurations tell the agent to do the same.
func sameConfig(a, b api.AgentConfig) bool {
	if a.Timezone != b.Timezone || a.Speedtest != b.Speedtest || len(a.ScheduleSlots) != len(b.ScheduleSlots) ||
		a.HeartbeatIntervalS != b.HeartbeatIntervalS || a.ConfigRefreshIntervalS != b.ConfigRefreshIntervalS {
		return false
	}
	for i, slot := range a.ScheduleSlots {
		if slot != b.ScheduleSlots[i] {
			return false
		}
	}
	return true
}

// runConfig keeps the configuration of the server up to date until ctx is
// done: the cached one first, then GET /api/agent/config at once and every
// config_refresh_interval_s (ТЗ п. 11, п. 20). apply gets every configuration
// that changed something, together with the schedule it describes; a
// configuration the agent cannot work by is logged and the old one stays.
func runConfig(ctx context.Context, client *api.Client, dataDir string, settings *Settings,
	apply func(api.AgentConfig, scheduler.Schedule), logger *slog.Logger,
) {
	var etag string
	if cached, err := readAgentConfig(dataDir); err == nil {
		if sched, err := agentSchedule(cached.Config); err == nil {
			etag = cached.ETag
			settings.set(cached.Config)
			logger.Info("конфигурация из кэша", "fetched_at", cached.FetchedAt, "etag", etag,
				"slots", len(cached.Config.ScheduleSlots))
			apply(cached.Config, sched)
		} else {
			logger.Warn("кэш конфигурации не годится, будет запрошена с сервера", "err", err)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		logger.Warn("кэш конфигурации не читается", "err", err)
	}

	var backoff api.Backoff
	for {
		wait := configRetryWait(settings)
		cfg, newETag, notModified, err := client.GetConfig(ctx, etag)
		switch {
		case ctx.Err() != nil:
			return
		case err != nil:
			wait = backoff.Next(err)
			logger.Warn("конфигурация не получена, повтор позже", "err", err, "retry_in", wait)
		case notModified:
			backoff.Reset()
			logger.Debug("конфигурация не изменилась", "etag", etag)
		default:
			backoff.Reset()
			sched, err := agentSchedule(cfg)
			if err != nil {
				logger.Error("сервер прислал неверную конфигурацию, работаем по прежней", "err", err)
				break
			}
			etag = newETag
			changed := !sameConfig(cfg, settings.Current())
			settings.set(cfg)
			if err := writeAgentConfig(dataDir, cachedConfig{ETag: etag, FetchedAt: time.Now(), Config: cfg}); err != nil {
				logger.Warn("кэш конфигурации не сохранён", "err", err)
			}
			if changed {
				logger.Info("конфигурация обновлена", "etag", etag, "timezone", cfg.Timezone,
					"slots", len(cfg.ScheduleSlots), "librespeed", cfg.Speedtest.LibreSpeedURL,
					"ndt7", cfg.Speedtest.NDT7URL, "refresh_s", cfg.ConfigRefreshIntervalS)
				apply(cfg, sched)
			}
			wait = configRetryWait(settings)
		}

		select {
		case <-ctx.Done():
			return
		case <-time.After(wait):
		}
	}
}

// configRefreshFallback is how long to wait for the next attempt while the
// agent has no configuration at all and the server is silent.
const configRefreshFallback = api.RetryFirst

// configRetryWait is config_refresh_interval_s of the current configuration.
func configRetryWait(settings *Settings) time.Duration {
	if s := settings.Current().ConfigRefreshIntervalS; s > 0 {
		return time.Duration(s) * time.Second
	}
	return configRefreshFallback
}
