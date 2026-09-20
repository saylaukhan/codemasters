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

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/queue"
	"github.com/saylaukhan/codemasters/agent/internal/scheduler"
	"github.com/saylaukhan/codemasters/agent/internal/secure"
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
	cfg Config
	// configPath is the file the service was registered with; the updater
	// process is started with the same one (T-50).
	configPath string
	logger     *slog.Logger
	cancel     context.CancelFunc
	done       chan struct{}
}

func (p *program) Start(kservice.Service) error {
	ctx, cancel := context.WithCancel(context.Background())
	p.cancel = cancel
	p.done = make(chan struct{})
	go func() {
		defer close(p.done)
		if err := runAgent(ctx, p.cfg, p.configPath, p.logger); err != nil {
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

// runAgent is the agent main loop: it records the start in the state file,
// opens the queue, registers the device (T-07), keeps the configuration of the
// server up to date, measures by its schedule (T-08, T-13), resends the queue
// (T-11), updates itself (T-50) and watches for a network change, until stop.
func runAgent(ctx context.Context, cfg Config, configPath string, logger *slog.Logger) error {
	st, err := ReadState(cfg.DataDir)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		logger.Warn("файл состояния повреждён, создаётся заново", "err", err)
	}
	st.Version = buildinfo.Version
	st.StartedAt = time.Now()
	if err := WriteState(cfg.DataDir, st); err != nil {
		return fmt.Errorf("запись состояния: %w", err)
	}

	q, err := queue.Open(QueuePath(cfg.DataDir), logger)
	if err != nil {
		return err
	}
	defer q.Close()

	logger.Info("агент запущен", "version", buildinfo.Version, "server_url", cfg.ServerURL,
		"data_dir", cfg.DataDir)
	// Not enrolled is not fatal: the reason is logged and the service keeps running;
	// measurements stay in the queue until the device is registered.
	id, token, ok := enroll(ctx, cfg, api.New(cfg.ServerURL, ""), logger)
	if ok {
		client := api.New(cfg.ServerURL, token)
		state := &stateFile{dir: cfg.DataDir, st: st, logger: logger}
		// wake asks the queue to resend at once: a new measurement, a restored
		// connection after a heartbeat or a network change (ADR-006).
		wake := make(chan struct{}, 1)
		settings := &Settings{}
		// beats tell the self-update that the server heard this version (T-50).
		beats := &beatClock{}

		go q.Run(ctx, client, wake, func(pending int) {
			state.update(func(s *State) { s.QueueSize = pending })
		})
		go watchNetwork(ctx, cfg.ServerURL, wake, logger)
		StartHeartbeat(ctx, HeartbeatOptions{
			Client: client,
			Queue:  q,
			// The interval is read before every heartbeat: a new value from
			// GET /api/agent/config applies without a restart (T-13), and
			// zero (no configuration yet) falls back to the default.
			Interval: func() time.Duration {
				return time.Duration(settings.Current().HeartbeatIntervalS) * time.Second
			},
			Wake:      wake,
			Logger:    logger,
			OnSuccess: beats.mark,
		})

		measure := measureFunc(cfg, client, q, settings, state, wake, logger)
		var sched *scheduler.Scheduler
		// apply runs only in the goroutine of runConfig, so sched is not shared.
		apply := func(ac api.AgentConfig, s scheduler.Schedule) {
			if sched != nil {
				sched.SetSchedule(s)
				return
			}
			sched = scheduler.New(scheduler.Options{
				Schedule: s,
				Seed:     id.DeviceUID,
				Last:     lastMeasurementAt(st),
				Measure:  measure,
				Logger:   logger,
			})
			go sched.Run(ctx)
		}
		go runConfig(ctx, client, cfg.DataDir, settings, apply, logger)
		startUpdates(ctx, cfg, configPath, client, settings, beats, logger)
	}
	<-ctx.Done()
	logger.Info("агент остановлен")
	return nil
}

// lastMeasurementAt is when the agent measured before this start; the zero
// time when it never did.
func lastMeasurementAt(st State) time.Time {
	if st.LastMeasurementAt == nil {
		return time.Time{}
	}
	return *st.LastMeasurementAt
}

// measureFunc is the callback of the scheduler: one measurement by the
// addresses of the current server configuration (ADR-012), into the queue,
// then a wake-up of the resend and the state file (plan.md §4.3, §4.4).
func measureFunc(cfg Config, client *api.Client, q *queue.Queue, settings *Settings, state *stateFile,
	wake chan<- struct{}, logger *slog.Logger,
) func(context.Context, scheduler.Run) {
	return func(ctx context.Context, _ scheduler.Run) {
		ac := settings.Current()
		m, err := Measure(ctx, MeasureOptions{
			ServerURL:     cfg.ServerURL,
			TargetURL:     ac.Speedtest.LibreSpeedURL,
			LibreSpeedURL: ac.Speedtest.LibreSpeedURL,
			NDT7URL:       ac.Speedtest.NDT7URL,
			Client:        client,
			Logger:        logger,
		})
		if err != nil {
			if ctx.Err() == nil {
				logger.Error("замер не выполнен", "err", err)
			}
			return
		}
		if err := q.Add(ctx, m); err != nil {
			logger.Error("замер не сохранён в очередь", "err", err)
			return
		}
		logger.Info("замер выполнен", "measurement_uuid", m.MeasurementUUID, "connection", m.ConnectionStatus)
		at := m.MeasuredAt
		state.update(func(s *State) { s.LastMeasurementAt = &at })
		select {
		case wake <- struct{}{}:
		default: // a wake-up is already pending
		}
	}
}

// QueuePath returns the measurement queue file inside dataDir.
func QueuePath(dataDir string) string {
	return filepath.Join(dataDir, queue.FileName)
}

// ReadToken returns the device token saved on registration (T-07).
func ReadToken(dataDir string) (string, error) {
	secret, err := secure.ReadSecret(filepath.Join(dataDir, tokenFileName))
	if err != nil {
		return "", fmt.Errorf("токен устройства: %w", err)
	}
	return string(secret), nil
}

// Run starts the agent: under the service manager as a service, from a
// terminal in the foreground until Ctrl+C (`make agent-run`).
func Run(cfg Config, configPath string, logger *slog.Logger) error {
	svc, err := kservice.New(&program{cfg: cfg, configPath: configPath, logger: logger}, definition(configPath))
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

// ApplyRecoveryActions sets the restart-after-failure policy on the installed
// service: 1 min, 1 min, 5 min (plan.md §4.1). Install does it right after
// registering the service; the MSI calls it separately, because it registers
// the service itself and the MSI table for these actions is documented by
// Microsoft as not working as expected (T-49).
func ApplyRecoveryActions() error {
	return setRecoveryActions(Name)
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
