package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
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

func TestRunWithExistingConfigSucceeds(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.yaml")
	if err := os.WriteFile(path, []byte("room: test\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	code, stdout, stderr := runCLI(t, "run", "--config", path)
	if code != exitOK {
		t.Fatalf("run with config: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
	if !strings.Contains(stdout, "T-06") {
		t.Fatalf("run with config: stdout %q does not name the follow-up task", stdout)
	}
}

// TestRunWithRepoDevConfig guards `make agent-run`, which passes ./dev.yaml
// relative to the agent/ directory.
func TestRunWithRepoDevConfig(t *testing.T) {
	code, _, stderr := runCLI(t, "run", "--config", filepath.Join("..", "..", "dev.yaml"))
	if code != exitOK {
		t.Fatalf("run with dev.yaml: exit code = %d, want %d; stderr: %s", code, exitOK, stderr)
	}
}

func TestStubCommandsSucceed(t *testing.T) {
	for _, name := range []string{"install", "status"} {
		code, stdout, stderr := runCLI(t, name)
		if code != exitOK {
			t.Fatalf("%s: exit code = %d, want %d; stderr: %s", name, code, exitOK, stderr)
		}
		if !strings.Contains(stdout, "T-06") {
			t.Fatalf("%s: stdout %q does not name the follow-up task", name, stdout)
		}
	}
}
