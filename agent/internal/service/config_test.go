package service

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestParseConfigFull(t *testing.T) {
	data := []byte(`
server_url: https://monitor.example.kz
room: "Кабинет 12"
enroll_code: VKO-7F3K-92QD
data_dir: /opt/vko
log_level: debug
`)
	cfg, err := ParseConfig(data, "/etc/vko-agent")
	if err != nil {
		t.Fatalf("ParseConfig: %v", err)
	}
	want := Config{
		ServerURL:  "https://monitor.example.kz",
		Room:       "Кабинет 12",
		EnrollCode: "VKO-7F3K-92QD",
		DataDir:    "/opt/vko",
		LogLevel:   "debug",
	}
	if cfg != want {
		t.Fatalf("ParseConfig = %+v, want %+v", cfg, want)
	}
}

func TestParseConfigDefaults(t *testing.T) {
	cfg, err := ParseConfig([]byte("server_url: http://localhost:8000\n"), "/etc/vko-agent")
	if err != nil {
		t.Fatalf("ParseConfig: %v", err)
	}
	if cfg.DataDir != DefaultDataDir() {
		t.Errorf("DataDir = %q, want default %q", cfg.DataDir, DefaultDataDir())
	}
	if cfg.LogLevel != DefaultLogLevel {
		t.Errorf("LogLevel = %q, want default %q", cfg.LogLevel, DefaultLogLevel)
	}
	if cfg.Room != "" || cfg.EnrollCode != "" {
		t.Errorf("Room/EnrollCode = %q/%q, want empty", cfg.Room, cfg.EnrollCode)
	}
}

func TestParseConfigRelativeDataDir(t *testing.T) {
	base := filepath.Join(t.TempDir(), "agent")
	cfg, err := ParseConfig([]byte("server_url: http://localhost:8000\ndata_dir: .data\n"), base)
	if err != nil {
		t.Fatalf("ParseConfig: %v", err)
	}
	if want := filepath.Join(base, ".data"); cfg.DataDir != want {
		t.Fatalf("DataDir = %q, want %q", cfg.DataDir, want)
	}
}

func TestParseConfigErrors(t *testing.T) {
	cases := map[string]struct {
		yaml string
		want string
	}{
		"empty file":         {"", "server_url"},
		"no server_url":      {"room: A\n", "server_url"},
		"server_url no host": {"server_url: localhost:8000\n", "server_url"},
		"server_url ftp":     {"server_url: ftp://example.kz\n", "server_url"},
		"bad log_level":      {"server_url: http://x\nlog_level: trace\n", "log_level"},
		"unknown key":        {"server_url: http://x\nserver_ulr: http://y\n", "server_ulr"},
		"broken yaml":        {"server_url: [\n", "разбор"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			_, err := ParseConfig([]byte(tc.yaml), t.TempDir())
			if err == nil {
				t.Fatalf("ParseConfig(%q): want error", tc.yaml)
			}
			if !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("ParseConfig(%q) error %q does not mention %q", tc.yaml, err, tc.want)
			}
		})
	}
}

// TestLoadRepoDevConfig guards `make agent-run`, which uses agent/dev.yaml.
func TestLoadRepoDevConfig(t *testing.T) {
	path := filepath.Join("..", "..", "dev.yaml")
	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatalf("LoadConfig(dev.yaml): %v", err)
	}
	abs, _ := filepath.Abs(filepath.Join("..", ".."))
	if !strings.HasPrefix(cfg.DataDir, abs) {
		t.Fatalf("dev.yaml DataDir = %q, want inside %q (make agent-run must not need admin rights)", cfg.DataDir, abs)
	}
}

func TestLoadConfigMissingFile(t *testing.T) {
	_, err := LoadConfig(filepath.Join(t.TempDir(), "missing.yaml"))
	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("LoadConfig(missing) error = %v, want os.ErrNotExist", err)
	}
}

func TestStateRoundTrip(t *testing.T) {
	dir := t.TempDir()
	if _, err := ReadState(dir); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("ReadState(empty dir) error = %v, want os.ErrNotExist", err)
	}
	measured := time.Date(2026, 9, 17, 12, 7, 0, 0, time.FixedZone("Asia/Almaty", 5*3600))
	want := State{Version: "1.0.0", StartedAt: measured.Add(-time.Hour), LastMeasurementAt: &measured, QueueSize: 3}
	if err := WriteState(dir, want); err != nil {
		t.Fatalf("WriteState: %v", err)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.Version != want.Version || !got.StartedAt.Equal(want.StartedAt) ||
		got.LastMeasurementAt == nil || !got.LastMeasurementAt.Equal(measured) || got.QueueSize != 3 {
		t.Fatalf("ReadState = %+v, want %+v", got, want)
	}
}
