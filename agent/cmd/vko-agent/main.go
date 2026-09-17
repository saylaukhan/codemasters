// Command vko-agent is the CLI of the school internet monitoring agent.
//
// Subcommands: install, uninstall, run, status, probe, speed, version. The service and the
// config live in internal/service; the measurement loop arrives in T-08+.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/netinfo"
	"github.com/saylaukhan/codemasters/agent/internal/probe"
	"github.com/saylaukhan/codemasters/agent/internal/service"
	"github.com/saylaukhan/codemasters/agent/internal/speed"
)

// Exit codes: 0 - success, 1 - runtime error, 2 - wrong usage (as in flag).
const (
	exitOK    = 0
	exitError = 1
	exitUsage = 2
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// run dispatches a subcommand and returns the process exit code. It is kept
// free of os.Exit so tests can call it with in-memory writers.
func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		printUsage(stderr)
		return exitUsage
	}

	switch args[0] {
	case "install":
		return cmdInstall(args[1:], stdout, stderr)
	case "uninstall":
		return cmdUninstall(args[1:], stdout, stderr)
	case "run":
		return cmdRun(args[1:], stdout, stderr)
	case "status":
		return cmdStatus(args[1:], stdout, stderr)
	case "probe":
		return cmdProbe(args[1:], stdout, stderr)
	case "speed":
		return cmdSpeed(args[1:], stdout, stderr)
	case "version":
		return cmdVersion(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		printUsage(stdout)
		return exitOK
	default:
		fmt.Fprintf(stderr, "vko-agent: неизвестная команда %q\n\n", args[0])
		printUsage(stderr)
		return exitUsage
	}
}

func printUsage(w io.Writer) {
	fmt.Fprint(w, `Использование: vko-agent <команда> [параметры]

Команды:
  install [--config <путь>]  установить и запустить службу VKOMonitorAgent
  uninstall                 остановить и удалить службу (данные остаются)
  run --config <путь>       запустить агента; без службы — до Ctrl+C
  status [--config <путь>]  показать состояние службы, последний замер и очередь
  probe [--config <путь>] [--target <url>]
                            проверить связь, ping/jitter/loss и сетевой адаптер
  speed --librespeed <url> [--ndt7 <url>]
                            замерить Download и Upload (LibreSpeed, резерв ndt7)
  version                   показать версию агента

Справка по команде: vko-agent <команда> -h
`)
}

// newFlagSet builds a flag set that reports errors to stderr instead of
// terminating the process and prints its help in Russian, like the rest of
// the CLI (the flag package's own header is English).
func newFlagSet(name string, stderr io.Writer) *flag.FlagSet {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.Usage = func() {
		hasFlags := false
		fs.VisitAll(func(*flag.Flag) { hasFlags = true })
		if !hasFlags {
			fmt.Fprintf(stderr, "Использование: vko-agent %s\n", name)
			return
		}
		fmt.Fprintf(stderr, "Использование: vko-agent %s [параметры]\n\nПараметры:\n", name)
		fs.PrintDefaults()
	}
	return fs
}

// parseFlags parses args and maps the outcome to an exit code. ok is false
// when the caller must stop and return code.
func parseFlags(fs *flag.FlagSet, args []string) (code int, ok bool) {
	err := fs.Parse(args)
	switch {
	case err == nil:
		return exitOK, true
	case errors.Is(err, flag.ErrHelp):
		return exitOK, false
	default:
		// The flag package has already printed its English error and the usage.
		fmt.Fprintf(fs.Output(), "%s: неверные параметры: %v\n", fs.Name(), err)
		return exitUsage, false
	}
}

func cmdInstall(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("install", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}

	abs, err := filepath.Abs(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "install: %v\n", err)
		return exitError
	}
	// Validate before registering: a service with a broken config would crash-loop.
	if _, err := service.LoadConfig(abs); err != nil {
		fmt.Fprintf(stderr, "install: %v\n", err)
		return exitError
	}
	if err := service.Install(abs); err != nil {
		fmt.Fprintf(stderr, "install: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Служба %s установлена и запущена (конфигурация: %s)\n", service.Name, abs)
	return exitOK
}

func cmdUninstall(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("uninstall", stderr)
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	if err := service.Uninstall(); err != nil {
		fmt.Fprintf(stderr, "uninstall: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Служба %s удалена; папка данных сохранена\n", service.Name)
	return exitOK
}

// cmdStatus prints the service state, the last measurement and the queue
// size (plan.md §4.1). It is a diagnostic tool, so it prints what it can
// even when the config or the state file is missing.
func cmdStatus(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("status", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}

	fmt.Fprintf(stdout, "Служба %s: %s\n", service.Name, service.ServiceStatus())
	fmt.Fprintf(stdout, "Версия агента: %s\n", buildinfo.Version)

	cfg, err := service.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "status: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Сервер: %s\n", cfg.ServerURL)
	fmt.Fprintf(stdout, "Папка данных: %s\n", cfg.DataDir)
	if id, err := service.ReadIdentity(cfg.DataDir); err == nil && id.DeviceID != 0 {
		fmt.Fprintf(stdout, "Устройство: зарегистрировано (device_id %d)\n", id.DeviceID)
	} else {
		fmt.Fprintln(stdout, "Устройство: не зарегистрировано")
	}

	st, err := service.ReadState(cfg.DataDir)
	switch {
	case errors.Is(err, os.ErrNotExist):
		fmt.Fprintln(stdout, "Последний замер: нет данных (агент ещё не запускался)")
		fmt.Fprintln(stdout, "Очередь на отправку: нет данных")
		return exitOK
	case err != nil:
		fmt.Fprintf(stderr, "status: %v\n", err)
		return exitError
	}

	fmt.Fprintf(stdout, "Запущен: %s\n", st.StartedAt.Format(time.RFC3339))
	if st.LastMeasurementAt == nil {
		fmt.Fprintln(stdout, "Последний замер: ещё не было")
	} else {
		fmt.Fprintf(stdout, "Последний замер: %s\n", st.LastMeasurementAt.Format(time.RFC3339))
	}
	fmt.Fprintf(stdout, "Очередь на отправку: %d\n", st.QueueSize)
	return exitOK
}

// cmdProbe runs the connectivity check, the ping series and the adapter
// detection once and prints them (plan.md §4.3, steps 1–3). The service gets
// the measurement server from GET /api/agent/config (T-13); here it is
// --target, the API server by default.
func cmdProbe(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("probe", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	target := fs.String("target", "", "адрес сервера замеров http(s)://хост; по умолчанию server_url")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	cfg, err := service.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "probe: %v\n", err)
		return exitError
	}
	if *target == "" {
		*target = cfg.ServerURL
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	res, err := probe.Run(ctx, probe.Options{
		ServerURL: cfg.ServerURL,
		TargetURL: *target,
		Logger:    slog.New(slog.NewTextHandler(stderr, nil)),
	})
	if err != nil {
		fmt.Fprintf(stderr, "probe: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Связь: %s\n", res.Status)
	if res.Status == probe.Offline {
		fmt.Fprintf(stdout, "Причина: %s\n", res.Reason)
		return exitOK
	}
	fmt.Fprintf(stdout, "Метод: %s до %s, ответов %d из %d\n", res.Method, res.Host, res.Received, res.Sent)
	fmt.Fprintf(stdout, "Ping: %.1f мс, Jitter: %.1f мс, Packet Loss: %.1f %%\n", res.PingMs, res.JitterMs, res.LossPct)

	info, err := netinfo.Detect(res.Host)
	if err != nil {
		fmt.Fprintf(stdout, "Адаптер: не определён (%v)\n", err)
		return exitOK
	}
	gateway := info.Gateway
	if gateway == "" {
		gateway = "неизвестен"
	}
	fmt.Fprintf(stdout, "Адаптер: %s (%s), адрес %s, шлюз %s\n", info.Interface, info.Type, info.LocalIP, gateway)
	return exitOK
}

// cmdSpeed measures Download and Upload once and prints them (plan.md §4.3,
// step 4). The service gets the server addresses from GET /api/agent/config
// (T-13); here they are flags without defaults, nothing is hard-coded (ADR-012).
func cmdSpeed(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("speed", stderr)
	libre := fs.String("librespeed", "", "адрес LibreSpeed http(s)://хост[:порт]")
	ndt7 := fs.String("ndt7", "", "адрес резервного сервера ndt7 ws(s)://хост[:порт]")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	if *libre == "" && *ndt7 == "" {
		fmt.Fprintln(stderr, "speed: укажите --librespeed и (или) --ndt7")
		return exitUsage
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	res, err := speed.Run(ctx, speed.Options{
		LibreSpeedURL: *libre,
		NDT7URL:       *ndt7,
		Logger:        slog.New(slog.NewTextHandler(stderr, nil)),
	})
	if err != nil {
		fmt.Fprintf(stderr, "speed: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Метод: %s, сервер %s\n", res.Method, res.Server)
	fmt.Fprintf(stdout, "Download: %.2f Мбит/с, Upload: %.2f Мбит/с, длительность %.1f с\n",
		res.DownloadMbps, res.UploadMbps, res.DurationS)
	if res.Fallback != "" {
		fmt.Fprintf(stdout, "Резерв: %s\n", res.Fallback)
	}
	return exitOK
}

func cmdVersion(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("version", stderr)
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	fmt.Fprintf(stdout, "vko-agent %s (%s/%s)\n", buildinfo.Version, runtime.GOOS, runtime.GOARCH)
	return exitOK
}

// cmdRun runs the agent: as a service when started by the service manager,
// in the foreground until Ctrl+C from a terminal. --check only validates the
// config and exits.
func cmdRun(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("run", stderr)
	configPath := fs.String("config", "", "путь к файлу конфигурации агента (YAML)")
	check := fs.Bool("check", false, "только проверить конфигурацию и выйти")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}

	if *configPath == "" {
		fmt.Fprintln(stderr, "run: не указан файл конфигурации, используйте --config <путь>")
		return exitUsage
	}

	abs, err := filepath.Abs(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "run: %v\n", err)
		return exitError
	}
	cfg, err := service.LoadConfig(abs)
	if err != nil {
		fmt.Fprintf(stderr, "run: %v\n", err)
		return exitError
	}

	if *check {
		fmt.Fprintf(stdout, "run: конфигурация %s в порядке (сервер %s, папка данных %s)\n",
			abs, cfg.ServerURL, cfg.DataDir)
		return exitOK
	}

	logger, closer, err := service.OpenLogger(cfg, stderr)
	if err != nil {
		fmt.Fprintf(stderr, "run: %v\n", err)
		return exitError
	}
	defer closer.Close()

	if err := service.Run(cfg, abs, logger); err != nil {
		logger.Error("служба завершилась с ошибкой", "err", err)
		return exitError
	}
	return exitOK
}
