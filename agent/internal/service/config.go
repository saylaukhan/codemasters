package service

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"runtime"

	"gopkg.in/yaml.v3"
)

// Config is the local agent configuration read from a YAML file.
//
// It holds only what the agent needs before it can talk to the server.
// Thresholds, the schedule and speedtest server addresses are never here:
// the agent gets them from GET /api/agent/config (ADR-004, T-13).
type Config struct {
	// ServerURL is the base URL of the monitoring API, e.g. https://monitor.example.kz.
	ServerURL string `yaml:"server_url"`
	// Room is the classroom the computer stands in; sent on registration (T-07).
	Room string `yaml:"room"`
	// EnrollCode is the one-time installation code (T-07); ENROLL_CODE is used when
	// empty. Ignored once the device is registered.
	EnrollCode string `yaml:"enroll_code"`
	// DataDir holds the state file, the log and, later, the queue and the token.
	// A relative path is resolved against the directory of the config file.
	DataDir string `yaml:"data_dir"`
	// LogLevel is one of debug, info, warn, error.
	LogLevel string `yaml:"log_level"`
}

// DefaultLogLevel is used when log_level is not set.
const DefaultLogLevel = "info"

var logLevels = map[string]bool{"debug": true, "info": true, "warn": true, "error": true}

// DefaultConfigPath is where `install` and `status` look for the config
// when --config is not given.
func DefaultConfigPath() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(programDataDir(), "agent.yaml")
	}
	return "/etc/vko-agent/agent.yaml"
}

// DefaultDataDir is the data directory used when data_dir is not set.
func DefaultDataDir() string {
	if runtime.GOOS == "windows" {
		return programDataDir()
	}
	return "/var/lib/vko-agent"
}

func programDataDir() string {
	base := os.Getenv("ProgramData")
	if base == "" {
		base = `C:\ProgramData`
	}
	return filepath.Join(base, "VKO Monitor")
}

// LoadConfig reads and validates the config file at path.
func LoadConfig(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("чтение конфигурации: %w", err)
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		return Config{}, fmt.Errorf("путь к конфигурации %s: %w", path, err)
	}
	return ParseConfig(data, filepath.Dir(abs))
}

// ParseConfig decodes YAML, applies defaults and validates the result.
// baseDir resolves a relative data_dir. Unknown keys are an error so that a
// typo in the file does not silently fall back to a default.
func ParseConfig(data []byte, baseDir string) (Config, error) {
	var cfg Config
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true)
	if err := dec.Decode(&cfg); err != nil && !errors.Is(err, io.EOF) {
		return Config{}, fmt.Errorf("разбор конфигурации: %w", err)
	}

	if cfg.DataDir == "" {
		cfg.DataDir = DefaultDataDir()
	} else if !filepath.IsAbs(cfg.DataDir) {
		cfg.DataDir = filepath.Join(baseDir, cfg.DataDir)
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = DefaultLogLevel
	}

	if err := cfg.validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func (c Config) validate() error {
	if c.ServerURL == "" {
		return errors.New("конфигурация: не задан server_url")
	}
	u, err := url.Parse(c.ServerURL)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return fmt.Errorf("конфигурация: server_url %q должен быть адресом http(s)://хост", c.ServerURL)
	}
	if !logLevels[c.LogLevel] {
		return fmt.Errorf("конфигурация: log_level %q — допустимо debug, info, warn, error", c.LogLevel)
	}
	return nil
}
