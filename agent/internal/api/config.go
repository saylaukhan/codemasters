package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
)

// ScheduleSlot is a measurement window of the day in the schedule time zone
// (backend/app/schemas/agent.py ScheduleSlot); times look like "08:30:00".
type ScheduleSlot struct {
	Start string `json:"start"`
	End   string `json:"end"`
}

// SpeedtestServers are the measurement servers: LibreSpeed is the main one,
// ndt7 the fallback (ADR-012). Addresses are never built into the agent.
type SpeedtestServers struct {
	LibreSpeedURL string `json:"librespeed_url"`
	NDT7URL       string `json:"ndt7_url,omitempty"`
}

// AgentConfig is the answer of GET /api/agent/config
// (backend/app/schemas/agent.py AgentConfigResponse): the schedule, the
// intervals and the measurement servers (ТЗ п. 11, п. 20; ADR-004).
//
// The thresholds of the answer are not read: the agent evaluates nothing,
// the server sets the status of a measurement (ADR-004).
type AgentConfig struct {
	// Timezone is the zone of the slot times, e.g. Asia/Almaty (ADR-014).
	Timezone      string         `json:"timezone"`
	ScheduleSlots []ScheduleSlot `json:"schedule_slots"`
	// HeartbeatIntervalS is how often the agent reports it is alive (T-12).
	HeartbeatIntervalS int `json:"heartbeat_interval_s"`
	// ConfigRefreshIntervalS is how often the agent asks for this answer again.
	ConfigRefreshIntervalS int              `json:"config_refresh_interval_s"`
	Speedtest              SpeedtestServers `json:"speedtest"`
	// LatestVersion is the agent version the server expects (T-50); empty when none.
	LatestVersion string `json:"latest_version,omitempty"`
	// TokenRotationRequired asks the agent to exchange its token with
	// POST /api/agent/token (T-36).
	TokenRotationRequired bool `json:"token_rotation_required,omitempty"`
}

// Validate checks what the agent depends on. The slot times and the time zone
// are checked by the scheduler, which builds the schedule from them.
func (c AgentConfig) Validate() error {
	if c.Timezone == "" {
		return errors.New("конфигурация сервера: пустой timezone")
	}
	if len(c.ScheduleSlots) == 0 {
		return errors.New("конфигурация сервера: расписание без слотов")
	}
	if c.HeartbeatIntervalS <= 0 || c.ConfigRefreshIntervalS <= 0 {
		return fmt.Errorf("конфигурация сервера: интервалы heartbeat_interval_s=%d и config_refresh_interval_s=%d должны быть больше нуля",
			c.HeartbeatIntervalS, c.ConfigRefreshIntervalS)
	}
	if u, err := url.Parse(c.Speedtest.LibreSpeedURL); err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return fmt.Errorf("конфигурация сервера: speedtest.librespeed_url %q должен быть адресом http(s)://хост", c.Speedtest.LibreSpeedURL)
	}
	return nil
}

// GetConfig asks the server for the agent configuration. When etag is not
// empty it is sent as If-None-Match: an unchanged configuration answers 304
// without a body (notModified), and nothing is transferred but the headers.
// On 200 the new ETag is returned along with the configuration.
func (c *Client) GetConfig(ctx context.Context, etag string) (cfg AgentConfig, newETag string, notModified bool, err error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/agent/config", nil)
	if err != nil {
		return AgentConfig{}, "", false, err
	}
	if etag != "" {
		req.Header.Set("If-None-Match", etag)
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return AgentConfig{}, "", false, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotModified {
		return AgentConfig{}, etag, true, nil
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return AgentConfig{}, "", false, problemFrom(resp)
	}
	if err := json.NewDecoder(resp.Body).Decode(&cfg); err != nil {
		return AgentConfig{}, "", false, fmt.Errorf("разбор конфигурации агента: %w", err)
	}
	return cfg, resp.Header.Get("ETag"), false, nil
}
