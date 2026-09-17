package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/service"
)

// runCLI invokes run with in-memory writers and returns the exit code and
// captured output.
func runCLI(t *testing.T, args ...string) (code int, stdout, stderr string) {
	t.Helper()
	var out, errOut bytes.Buffer
	code = run(args, &out, &errOut)
	return code, out.String(), errOut.String()
}

func TestVersionPrintsVersion(t *testing.T) {
	code, stdout, stderr := runCLI(t, "version")
	if code != exitOK {
		t.Fatalf("version: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
	if !strings.Contains(stdout, buildinfo.Version) {
		t.Fatalf("version: stdout %q does not contain %q", stdout, buildinfo.Version)
	}
}

func TestNoCommandIsUsageError(t *testing.T) {
	code, _, stderr := runCLI(t)
	if code != exitUsage {
		t.Fatalf("no command: exit code = %d, want %d", code, exitUsage)
	}
	if !strings.Contains(stderr, "vko-agent <команда>") {
		t.Fatalf("no command: stderr %q does not contain usage", stderr)
	}
}

func TestUnknownCommandIsUsageError(t *testing.T) {
	code, _, stderr := runCLI(t, "frobnicate")
	if code != exitUsage {
		t.Fatalf("unknown command: exit code = %d, want %d", code, exitUsage)
	}
	if !strings.Contains(stderr, "frobnicate") {
		t.Fatalf("unknown command: stderr %q does not mention the command", stderr)
	}
}

func TestCommandHelpIsRussian(t *testing.T) {
	code, _, stderr := runCLI(t, "run", "-h")
	if code != exitOK {
		t.Fatalf("run -h: exit code = %d, want %d", code, exitOK)
	}
	if !strings.Contains(stderr, "Использование: vko-agent run") || !strings.Contains(stderr, "-config") {
		t.Fatalf("run -h: stderr %q is not the Russian usage with the -config flag", stderr)
	}
}

func TestUnknownFlagIsUsageError(t *testing.T) {
	code, _, stderr := runCLI(t, "run", "--bogus")
	if code != exitUsage {
		t.Fatalf("run --bogus: exit code = %d, want %d", code, exitUsage)
	}
	if !strings.Contains(stderr, "неверные параметры") {
		t.Fatalf("run --bogus: stderr %q has no Russian hint", stderr)
	}
}

func TestRunWithoutConfigIsUsageError(t *testing.T) {
	code, _, stderr := runCLI(t, "run")
	if code != exitUsage {
		t.Fatalf("run without --config: exit code = %d, want %d", code, exitUsage)
	}
	if !strings.Contains(stderr, "--config") {
		t.Fatalf("run without --config: stderr %q does not mention --config", stderr)
	}
}

func TestRunWithMissingConfigFails(t *testing.T) {
	missing := filepath.Join(t.TempDir(), "missing.yaml")
	code, _, stderr := runCLI(t, "run", "--config", missing)
	if code != exitError {
		t.Fatalf("run with missing config: exit code = %d, want %d", code, exitError)
	}
	if !strings.Contains(stderr, "missing.yaml") {
		t.Fatalf("run with missing config: stderr %q does not mention the path", stderr)
	}
}

func TestRunWithInvalidConfigFails(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.yaml")
	if err := os.WriteFile(path, []byte("room: test\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	code, _, stderr := runCLI(t, "run", "--config", path, "--check")
	if code != exitError {
		t.Fatalf("run with invalid config: exit code = %d, want %d", code, exitError)
	}
	if !strings.Contains(stderr, "server_url") {
		t.Fatalf("run with invalid config: stderr %q does not name the missing field", stderr)
	}
}

func TestRunCheckWithValidConfig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.yaml")
	if err := os.WriteFile(path, []byte("server_url: http://localhost:8000\nroom: test\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	code, stdout, stderr := runCLI(t, "run", "--config", path, "--check")
	if code != exitOK {
		t.Fatalf("run --check: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
	if !strings.Contains(stdout, "http://localhost:8000") {
		t.Fatalf("run --check: stdout %q does not show the server", stdout)
	}
}

// TestRunWithRepoDevConfig guards `make agent-run`, which passes ./dev.yaml
// relative to the agent/ directory.
func TestRunWithRepoDevConfig(t *testing.T) {
	code, _, stderr := runCLI(t, "run", "--config", filepath.Join("..", "..", "dev.yaml"), "--check")
	if code != exitOK {
		t.Fatalf("run with dev.yaml: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
}

func TestStatusWithoutStateFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "agent.yaml")
	cfg := "server_url: http://localhost:8000\ndata_dir: data\n"
	if err := os.WriteFile(path, []byte(cfg), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	code, stdout, stderr := runCLI(t, "status", "--config", path)
	if code != exitOK {
		t.Fatalf("status: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
	for _, want := range []string{"Служба VKOMonitorAgent:", "Последний замер: нет данных", "Очередь на отправку"} {
		if !strings.Contains(stdout, want) {
			t.Fatalf("status: stdout %q does not contain %q", stdout, want)
		}
	}
}

func TestStatusShowsState(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "agent.yaml")
	if err := os.WriteFile(path, []byte("server_url: http://localhost:8000\ndata_dir: data\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	dataDir := filepath.Join(dir, "data")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	measured := time.Date(2026, 9, 17, 12, 7, 0, 0, time.FixedZone("", 5*3600))
	st := service.State{Version: "dev", StartedAt: measured.Add(-time.Hour), LastMeasurementAt: &measured, QueueSize: 7}
	if err := service.WriteState(dataDir, st); err != nil {
		t.Fatalf("WriteState: %v", err)
	}
	code, stdout, stderr := runCLI(t, "status", "--config", path)
	if code != exitOK {
		t.Fatalf("status: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
	for _, want := range []string{"Последний замер: 2026-09-17T12:07:00+05:00", "Очередь на отправку: 7"} {
		if !strings.Contains(stdout, want) {
			t.Fatalf("status: stdout %q does not contain %q", stdout, want)
		}
	}
}

func TestStatusWithMissingConfigFails(t *testing.T) {
	code, stdout, stderr := runCLI(t, "status", "--config", filepath.Join(t.TempDir(), "missing.yaml"))
	if code != exitError {
		t.Fatalf("status without config: exit code = %d, want %d", code, exitError)
	}
	if !strings.Contains(stdout, "Служба VKOMonitorAgent:") || !strings.Contains(stderr, "missing.yaml") {
		t.Fatalf("status without config: stdout %q / stderr %q", stdout, stderr)
	}
}
