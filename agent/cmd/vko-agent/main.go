// Command vko-agent is the CLI of the school internet monitoring agent.
//
// Subcommands: configure, install, uninstall, run, status, probe, speed, measure, update-apply,
// version. The service, its loop (schedule, measurements, resend) and the config live in
// internal/service.
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

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/netinfo"
	"github.com/saylaukhan/codemasters/agent/internal/probe"
	"github.com/saylaukhan/codemasters/agent/internal/queue"
	"github.com/saylaukhan/codemasters/agent/internal/service"
	"github.com/saylaukhan/codemasters/agent/internal/speed"
	"github.com/saylaukhan/codemasters/agent/internal/update"
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
	case "configure":
		return cmdConfigure(args[1:], stdout, stderr)
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
	case "measure":
		return cmdMeasure(args[1:], stdout, stderr)
	case "update-apply":
		return cmdUpdateApply(args[1:], stdout, stderr)
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
  configure --config <путь> --server-url <url> [--enroll-code <код>] [--room <кабинет>]
            [--data-dir <папка>] [--log-level <уровень>]
                            создать или обновить файл конфигурации (вызывают установщики)
  install [--config <путь>]  установить и запустить службу агента
  uninstall                 остановить и удалить службу (данные остаются)
  run --config <путь>       запустить агента; без службы — до Ctrl+C
  status [--config <путь>]  показать состояние службы, последний замер и очередь
  probe [--config <путь>] [--target <url>]
                            проверить связь, ping/jitter/loss и сетевой адаптер
  speed --librespeed <url> [--ndt7 <url>]
                            замерить Download и Upload (LibreSpeed, резерв ndt7)
  measure [--config <путь>] [--target <url>] [--librespeed <url>] [--ndt7 <url>]
                            один замер: в очередь и сразу отправить на сервер
  update-apply --msi <путь> [--config <путь>] [--version <версия>] [--remove <путь>]
                            установить скачанный релиз; запускает служба при обновлении
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

// cmdConfigure creates or updates the agent configuration file from the
// installation parameters: the MSI custom action calls it with ENROLL_CODE
// and ROOM from the silent install command line (plan.md §4.1, T-49), and the
// postinstall of the Linux package with the same values from its environment
// (installer/linux, T-52).
//
// An empty value keeps what the existing file has, so a repair or an upgrade
// does not lose the enrollment code or a room edited by hand. Nothing else is
// configurable here: thresholds, the schedule and the address of the
// measurement server come from the server (ADR-004, ADR-012).
func cmdConfigure(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("configure", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	serverURL := fs.String("server-url", "", "адрес API сервера мониторинга http(s)://хост")
	enrollCode := fs.String("enroll-code", "", "одноразовый код установки (T-07)")
	room := fs.String("room", "", "кабинет, в котором стоит компьютер")
	dataDir := fs.String("data-dir", "", "папка состояния, журнала и очереди замеров")
	logLevel := fs.String("log-level", "", "уровень журнала: debug, info, warn, error")
	recovery := fs.Bool("service-recovery", false, "задать перезапуск службы после сбоя (1 / 1 / 5 мин)")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}

	abs, err := filepath.Abs(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "configure: %v\n", err)
		return exitError
	}

	// A file that does not load yet (first install) or is broken is rewritten
	// in full; a readable one keeps the values no flag overrides.
	cfg, err := service.LoadConfig(abs)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		fmt.Fprintf(stderr, "configure: прежняя конфигурация не прочитана, файл будет перезаписан: %v\n", err)
	}
	keepNonEmpty(&cfg.ServerURL, *serverURL)
	keepNonEmpty(&cfg.EnrollCode, *enrollCode)
	keepNonEmpty(&cfg.Room, *room)
	keepNonEmpty(&cfg.DataDir, *dataDir)
	keepNonEmpty(&cfg.LogLevel, *logLevel)
	if cfg.DataDir == "" {
		cfg.DataDir = service.DefaultDataDir()
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = service.DefaultLogLevel
	}

	if err := service.WriteConfig(abs, cfg); err != nil {
		fmt.Fprintf(stderr, "configure: %v\n", err)
		return exitError
	}
	// The enrollment code is not printed: the installer log is world-readable.
	fmt.Fprintf(stdout, "Конфигурация записана: %s (сервер %s, папка данных %s)\n",
		abs, cfg.ServerURL, cfg.DataDir)

	// The service is already registered by then (the MSI does it itself), so a
	// failure here leaves a working service without a restart policy — worth a
	// line in the installer log, not a reason to roll the installation back.
	if *recovery {
		if err := service.ApplyRecoveryActions(); err != nil {
			fmt.Fprintf(stderr, "configure: перезапуск службы после сбоя не задан: %v\n", err)
		} else {
			fmt.Fprintln(stdout, "Перезапуск службы после сбоя: 1 / 1 / 5 мин")
		}
	}
	return exitOK
}

// keepNonEmpty overwrites *dst with value unless value is empty. The MSI
// custom action always passes every flag, and an unset install property
// arrives as an empty string.
func keepNonEmpty(dst *string, value string) {
	if value != "" {
		*dst = value
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
		if n, ok := queuePending(cfg); ok {
			fmt.Fprintf(stdout, "Очередь на отправку: %d\n", n)
		} else {
			fmt.Fprintln(stdout, "Очередь на отправку: нет данных")
		}
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
	if n, ok := queuePending(cfg); ok {
		st.QueueSize = n
	}
	fmt.Fprintf(stdout, "Очередь на отправку: %d\n", st.QueueSize)
	return exitOK
}

// queuePending counts the queue file when it exists: a measurement taken by
// `measure` is not in the state file of the service.
func queuePending(cfg service.Config) (int, bool) {
	if _, err := os.Stat(service.QueuePath(cfg.DataDir)); err != nil {
		return 0, false
	}
	q, err := queue.Open(service.QueuePath(cfg.DataDir), nil)
	if err != nil {
		return 0, false
	}
	defer q.Close()
	n, err := q.Pending(context.Background())
	return n, err == nil
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

// cmdMeasure takes one measurement, puts it into the queue and sends the
// queue (plan.md §4.3, §4.4). Without a connection or a registration the
// measurement stays in the queue for the service to resend (ADR-006).
func cmdMeasure(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("measure", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	target := fs.String("target", "", "адрес сервера замеров http(s)://хост; по умолчанию server_url")
	libre := fs.String("librespeed", "", "адрес LibreSpeed http(s)://хост[:порт]; без него скорость не замеряется")
	ndt7 := fs.String("ndt7", "", "адрес резервного сервера ndt7 ws(s)://хост[:порт]")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	cfg, err := service.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "measure: %v\n", err)
		return exitError
	}
	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		fmt.Fprintf(stderr, "measure: %v\n", err)
		return exitError
	}
	logger := slog.New(slog.NewTextHandler(stderr, nil))
	q, err := queue.Open(service.QueuePath(cfg.DataDir), logger)
	if err != nil {
		fmt.Fprintf(stderr, "measure: %v\n", err)
		return exitError
	}
	defer q.Close()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	opts := service.MeasureOptions{
		ServerURL:     cfg.ServerURL,
		TargetURL:     *target,
		LibreSpeedURL: *libre,
		NDT7URL:       *ndt7,
		Logger:        logger,
	}
	token, tokenErr := service.ReadToken(cfg.DataDir)
	if tokenErr == nil {
		opts.Client = api.New(cfg.ServerURL, token)
	}
	m, err := service.Measure(ctx, opts)
	if err != nil {
		fmt.Fprintf(stderr, "measure: %v\n", err)
		return exitError
	}
	if err := q.Add(ctx, m); err != nil {
		fmt.Fprintf(stderr, "measure: %v\n", err)
		return exitError
	}
	fmt.Fprintf(stdout, "Замер %s: связь %s, в очереди\n", m.MeasurementUUID, m.ConnectionStatus)

	if tokenErr != nil {
		fmt.Fprintf(stdout, "Отправка: устройство не зарегистрировано (%v)\n", tokenErr)
	} else if sent, err := q.Flush(ctx, opts.Client); err != nil {
		fmt.Fprintf(stdout, "Отправка: отправлено %d, остальное позже (%v)\n", sent, err)
	} else {
		fmt.Fprintf(stdout, "Отправка: отправлено %d\n", sent)
	}
	if n, err := q.Pending(ctx); err == nil {
		fmt.Fprintf(stdout, "Очередь на отправку: %d\n", n)
	}
	return exitOK
}

// cmdUpdateApply installs a downloaded release. It is the separate updater
// process the service starts and then dies with: msiexec stops the service
// VKOMonitorAgent, so the installation cannot run inside it (plan.md §4.6,
// T-50). It is not meant to be run by hand — the service passes the file it
// has already checked by SHA-256 and by signature.
//
// --remove uninstalls the installation that is there now before installing;
// a rollback needs it, because the package refuses to install over a newer
// version (installer/wix/Package.wxs, MajorUpgrade).
func cmdUpdateApply(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("update-apply", stderr)
	configPath := fs.String("config", service.DefaultConfigPath(), "путь к файлу конфигурации агента (YAML)")
	msi := fs.String("msi", "", "путь к установщику MSI, который нужно установить")
	version := fs.String("version", "", "версия, которая устанавливается (для журнала)")
	remove := fs.String("remove", "", "путь к MSI прежней установки: снять её перед установкой (откат)")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	if *msi == "" {
		fmt.Fprintln(stderr, "update-apply: не указан установщик, используйте --msi <путь>")
		return exitUsage
	}

	cfg, err := service.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "update-apply: %v\n", err)
		return exitError
	}
	// The log of the agent is the only place a silent installation on a school
	// computer can be explained from afterwards.
	logger, closer, err := service.OpenLogger(cfg, stderr)
	if err != nil {
		fmt.Fprintf(stderr, "update-apply: %v\n", err)
		return exitError
	}
	defer closer.Close()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	if err := update.Install(ctx, update.InstallOptions{
		DataDir: cfg.DataDir,
		MSI:     *msi,
		Version: *version,
		Remove:  *remove,
		Logger:  logger,
	}); err != nil {
		logger.Error("обновление не установлено", "version", *version, "msi", *msi, "err", err)
		return exitError
	}
	logger.Info("обновление установлено", "version", *version, "msi", *msi)
	fmt.Fprintf(stdout, "Обновление установлено: %s\n", *msi)
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
