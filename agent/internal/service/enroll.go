package service

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/secure"
)

const (
	// identityFileName keeps the public part of the device identity; `status` reads it.
	identityFileName = "device.json"
	// tokenFileName keeps the device token sealed by package secure (ADR-005).
	tokenFileName = "device_token"
	// enrollCodeEnv is the enrollment code for a silent install (ENROLL_CODE, plan.md §4.1)
	// when the config has none.
	enrollCodeEnv = "ENROLL_CODE"
)

// enrollRetryFirst and enrollRetryMax bound the pause between registration
// attempts while the server is unreachable or failing. Variables for tests.
var (
	enrollRetryFirst = 30 * time.Second
	enrollRetryMax   = 15 * time.Minute
)

// Identity is the device identity kept in DataDir/device.json. DeviceUID is
// generated once and survives failed registrations; DeviceID is set after the
// server accepted the enrollment code. The token is never in this file.
type Identity struct {
	DeviceUID    string     `json:"device_uid"`
	DeviceID     int64      `json:"device_id,omitempty"`
	RegisteredAt *time.Time `json:"registered_at,omitempty"`
}

// ReadIdentity reads DataDir/device.json. A missing file returns an error that
// satisfies errors.Is(err, os.ErrNotExist).
func ReadIdentity(dataDir string) (Identity, error) {
	path := filepath.Join(dataDir, identityFileName)
	data, err := os.ReadFile(path)
	if err != nil {
		return Identity{}, err
	}
	var id Identity
	if err := json.Unmarshal(data, &id); err != nil {
		return Identity{}, fmt.Errorf("разбор %s: %w", path, err)
	}
	return id, nil
}

func writeIdentity(dataDir string, id Identity) error {
	data, err := json.MarshalIndent(id, "", "  ")
	if err != nil {
		return err
	}
	path := filepath.Join(dataDir, identityFileName)
	if err := os.WriteFile(path+".tmp", data, 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}

// enroll makes sure the device is registered and returns its identity and
// token. A device registered earlier is not registered again. ok is false
// when there is no code, the server rejected it or ctx was cancelled: the
// reason is logged and the service keeps running (T-07).
func enroll(ctx context.Context, cfg Config, client *api.Client, logger *slog.Logger) (id Identity, token string, ok bool) {
	id, err := ReadIdentity(cfg.DataDir)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		logger.Warn("файл устройства повреждён, создаётся заново", "err", err)
	}
	tokenPath := filepath.Join(cfg.DataDir, tokenFileName)

	if id.DeviceID != 0 {
		secret, err := secure.ReadSecret(tokenPath)
		if err == nil {
			logger.Info("устройство зарегистрировано ранее", "device_id", id.DeviceID)
			return id, string(secret), true
		}
		logger.Error("токен устройства не читается, нужна регистрация по новому коду",
			"device_id", id.DeviceID, "err", err)
		id.DeviceID, id.RegisteredAt = 0, nil
	}

	code := cfg.EnrollCode
	if code == "" {
		code = os.Getenv(enrollCodeEnv)
	}
	if code == "" {
		logger.Warn("устройство не зарегистрировано: нет кода установки (enroll_code в конфигурации или " + enrollCodeEnv + ")")
		return id, "", false
	}

	if id.DeviceUID == "" {
		if id.DeviceUID, err = newDeviceUID(); err != nil {
			logger.Error("не удалось создать идентификатор устройства", "err", err)
			return id, "", false
		}
		if err := writeIdentity(cfg.DataDir, id); err != nil {
			logger.Error("запись файла устройства", "err", err)
			return id, "", false
		}
	}

	hostname, _ := os.Hostname()
	req := api.RegisterRequest{
		EnrollmentCode: code,
		DeviceUID:      id.DeviceUID,
		Hostname:       hostname,
		OS:             runtime.GOOS + "/" + runtime.GOARCH,
		AgentVersion:   buildinfo.Version,
		Room:           cfg.Room,
	}

	delay := enrollRetryFirst
	for {
		resp, err := client.Register(ctx, req)
		if err == nil {
			if err := secure.WriteSecret(tokenPath, []byte(resp.DeviceToken)); err != nil {
				logger.Error("регистрация прошла, но токен не сохранён", "device_id", resp.DeviceID, "err", err)
				return id, "", false
			}
			now := time.Now()
			id.DeviceID, id.RegisteredAt = resp.DeviceID, &now
			if err := writeIdentity(cfg.DataDir, id); err != nil {
				logger.Error("регистрация прошла, но файл устройства не сохранён", "device_id", resp.DeviceID, "err", err)
				return id, "", false
			}
			logger.Info("устройство зарегистрировано", "device_id", resp.DeviceID)
			return id, resp.DeviceToken, true
		}
		if ctx.Err() != nil {
			return id, "", false
		}

		var pe *api.ProblemError
		if errors.As(err, &pe) && !pe.Temporary() {
			logger.Error("сервер отклонил код установки: нужен новый код", "status", pe.Status,
				"type", pe.Type, "detail", pe.Detail)
			return id, "", false
		}

		logger.Warn("регистрация не удалась, повтор позже", "err", err, "retry_in", delay)
		select {
		case <-ctx.Done():
			return id, "", false
		case <-time.After(delay):
		}
		delay = min(delay*2, enrollRetryMax)
	}
}

// newDeviceUID returns a random 128-bit identifier of this installation.
func newDeviceUID() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
