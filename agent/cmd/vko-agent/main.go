// Command vko-agent is the CLI of the school internet monitoring agent.
//
// Subcommands: install, run, status, version. In T-01 they are skeleton
// stubs without external dependencies; the service, the YAML config parser
// and the measurement loop arrive in T-06 and later tasks.
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"runtime"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
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
	case "run":
		return cmdRun(args[1:], stdout, stderr)
	case "status":
		return cmdStatus(args[1:], stdout, stderr)
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
  install                установить службу VKOMonitorAgent (появится в T-06)
  run --config <путь>    запустить агента в текущем процессе с файлом конфигурации
  status                 показать состояние службы, последний замер и очередь (T-06)
  version                показать версию агента

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
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	fmt.Fprintln(stdout, "install: установка службы VKOMonitorAgent появится в T-06")
	return exitOK
}

func cmdStatus(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("status", stderr)
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}
	fmt.Fprintln(stdout, "status: состояние службы, последний замер и размер очереди появятся в T-06")
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

// cmdRun checks that the config file exists. Parsing it and starting the
// measurement loop is T-06; for now the command only validates the path.
func cmdRun(args []string, stdout, stderr io.Writer) int {
	fs := newFlagSet("run", stderr)
	configPath := fs.String("config", "", "путь к файлу конфигурации агента (YAML)")
	if code, ok := parseFlags(fs, args); !ok {
		return code
	}

	if *configPath == "" {
		fmt.Fprintln(stderr, "run: не указан файл конфигурации, используйте --config <путь>")
		return exitUsage
	}

	info, err := os.Stat(*configPath)
	if err != nil {
		fmt.Fprintf(stderr, "run: файл конфигурации недоступен: %v\n", err)
		return exitError
	}
	if info.IsDir() {
		fmt.Fprintf(stderr, "run: %s — это папка, а не файл конфигурации\n", *configPath)
		return exitError
	}

	fmt.Fprintf(stdout, "run: файл конфигурации %s найден; разбор YAML, служба и цикл замеров появятся в T-06\n",
		*configPath)
	return exitOK
}
