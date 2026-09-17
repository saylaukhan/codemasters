// Package service runs the agent as a Windows service or a systemd unit
// (kardianos/service) and reads the local agent configuration.
//
// The agent has no GUI and no tray icon (ADR-010): after installation the
// service starts with the OS and needs no user action (ТЗ п. 2).
package service

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"

	kservice "github.com/kardianos/service"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
)

// Service identity; the MSI (plan.md §4.1) uses the same name.
const (
	Name        = "VKOMonitorAgent"
	DisplayName = "Мониторинг интернета ВКО"
	Description = "Фоновые замеры качества интернет-соединения школы и отправка результатов на сервер мониторинга."
)

// stopTimeout bounds how long Stop waits for the agent loop to finish.
const stopTimeout = 10 * time.Second

// Status of the installed service as shown by `vko-agent status`.
type Status string

const (
	StatusRunning      Status = "работает"
	StatusStopped      Status = "остановлена"
	StatusNotInstalled Status = "не установлена"
	StatusUnknown      Status = "неизвестно"
)

// definition describes the service for kardianos/service. configPath must be
// absolute: the service manager starts the binary from another directory.
func definition(configPath string) *kservice.Config {
	return &kservice.Config{
		Name:        Name,
		DisplayName: DisplayName,
		Description: Description,
		Arguments:   []string{"run", "--config", configPath},
		UserName:    windowsUserName,
		Option: kservice.KeyValue{
			// Windows: "Automatic (Delayed Start)"; recovery actions are set in setRecoveryActions.
			"DelayedAutoStart": true,
			// systemd: Restart=on-failure.
			"Restart": "on-failure",
		},
	}
}

// program adapts the agent loop to kardianos/service Start/Stop.
type program struct {
	cfg    Config
	logger *slog.Logger
	cancel context.CancelFunc
	done   chan struct{}
}

func (p *program) Start(kservice.Service) error {
	ctx, cancel := context.WithCancel(context.Background())
	p.cancel = cancel
	p.done = make(chan struct{})
	go func() {
		defer close(p.done)
		if err := runAgent(ctx, p.cfg, p.logger); err != nil {
			p.logger.Error("агент остановлен с ошибкой", "err", err)
			// Exit non-zero so the service manager applies the restart policy.
			os.Exit(1)
		}
	}()
	return nil
}

func (p *program) Stop(kservice.Service) error {
	p.cancel()
	select {
	case <-p.done:
	case <-time.After(stopTimeout):
		p.logger.Warn("агент не остановился вовремя", "timeout", stopTimeout)
	}
	return nil
}

// runAgent is the agent main loop. In T-06 it records the start in the state
// file and waits for stop; registration (T-07), the scheduler (T-08) and the
// queue (T-11) plug in here.
func runAgent(ctx context.Context, cfg Config, logger *slog.Logger) error {
	st, err := ReadState(cfg.DataDir)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		logger.Warn("файл состояния повреждён, создаётся заново", "err", err)
	}
	st.Version = buildinfo.Version
	st.StartedAt = time.Now()
	if err := WriteState(cfg.DataDir, st); err != nil {
		return fmt.Errorf("запись состояния: %w", err)
	}

	logger.Info("агент запущен", "version", buildinfo.Version, "server_url", cfg.ServerURL,
		"data_dir", cfg.DataDir)
	<-ctx.Done()
	logger.Info("агент остановлен")
	return nil
}

// Run starts the agent: under the service manager as a service, from a
// terminal in the foreground until Ctrl+C (`make agent-run`).
func Run(cfg Config, configPath string, logger *slog.Logger) error {
	svc, err := kservice.New(&program{cfg: cfg, logger: logger}, definition(configPath))
	if err != nil {
		return err
	}
	return svc.Run()
}

// Install registers the service with the OS and starts it.
func Install(configPath string) error {
	svc, err := kservice.New(&program{}, definition(configPath))
	if err != nil {
		return err
	}
	if err := svc.Install(); err != nil {
		return fmt.Errorf("регистрация службы: %w", err)
	}
	if err := setRecoveryActions(Name); err != nil {
		return fmt.Errorf("настройка перезапуска при сбое: %w", err)
	}
	if err := svc.Start(); err != nil {
		return fmt.Errorf("служба зарегистрирована, но не запустилась: %w", err)
	}
	return nil
}

// Uninstall stops the service and removes it. The data directory stays:
// the queue must survive reinstallation (ADR-006).
func Uninstall() error {
	svc, err := kservice.New(&program{}, definition(""))
	if err != nil {
		return err
	}
	_ = svc.Stop() // already stopped is fine
	if err := svc.Uninstall(); err != nil {
		return fmt.Errorf("удаление службы: %w", err)
	}
	return nil
}

// ServiceStatus asks the OS service manager about the service.
func ServiceStatus() Status {
	svc, err := kservice.New(&program{}, definition(""))
	if err != nil {
		return StatusUnknown
	}
	st, err := svc.Status()
	switch {
	case errors.Is(err, kservice.ErrNotInstalled):
		return StatusNotInstalled
	case err != nil:
		return StatusUnknown
	case st == kservice.StatusRunning:
		return StatusRunning
	case st == kservice.StatusStopped:
		return StatusStopped
	default:
		return StatusUnknown
	}
}

// OpenLogger creates DataDir and returns a logger that writes to stderr and
// to DataDir/agent.log (a Windows service has no console). Close the
// returned closer on exit.
func OpenLogger(cfg Config, stderr io.Writer) (*slog.Logger, io.Closer, error) {
	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		return nil, nil, fmt.Errorf("папка данных %s: %w", cfg.DataDir, err)
	}
	f, err := os.OpenFile(filepath.Join(cfg.DataDir, "agent.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, nil, fmt.Errorf("файл журнала: %w", err)
	}
	var level slog.Level
	if err := level.UnmarshalText([]byte(strings.ToUpper(cfg.LogLevel))); err != nil {
		level = slog.LevelInfo
	}
	h := slog.NewTextHandler(io.MultiWriter(stderr, f), &slog.HandlerOptions{Level: level})
	return slog.New(h), f, nil
}
