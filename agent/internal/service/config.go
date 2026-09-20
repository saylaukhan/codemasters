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
	"strconv"
	"strings"

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

// WriteConfig writes cfg to path as a commented YAML file, creating the
// parent directory. It is how the MSI custom action creates agent.yaml from
// the install properties (T-49, plan.md §4.1), so the file stays readable:
// an administrator edits the same file by hand afterwards.
func WriteConfig(path string, cfg Config) error {
	if err := cfg.validate(); err != nil {
		return err
	}
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("папка конфигурации %s: %w", dir, err)
	}
	// 0600: the enrollment code is in the file. On Windows the mode is not an
	// ACL — access for the service account comes from the folder (T-49).
	if err := os.WriteFile(path+".tmp", []byte(renderConfig(cfg)), 0o600); err != nil {
		return fmt.Errorf("запись конфигурации: %w", err)
	}
	if err := os.Rename(path+".tmp", path); err != nil {
		return fmt.Errorf("запись конфигурации: %w", err)
	}
	return nil
}

// renderConfig builds the YAML text of cfg. The comments repeat agent/dev.yaml
// so both files read the same.
func renderConfig(cfg Config) string {
	var b strings.Builder
	b.WriteString("# Конфигурация агента «Мониторинг интернета ВКО».\n")
	b.WriteString("# Файл создан установщиком; правится вручную, служба перечитывает его при перезапуске.\n")
	b.WriteString("# Пороги, расписание и адрес сервера замеров сюда не пишутся — агент получает их\n")
	b.WriteString("# с сервера (GET /api/agent/config, ADR-004, ADR-012).\n\n")
	b.WriteString("# Адрес API сервера мониторинга.\n")
	b.WriteString("server_url: " + yamlValue(cfg.ServerURL) + "\n\n")
	b.WriteString("# Кабинет, в котором стоит этот компьютер (попадает в точку мониторинга).\n")
	b.WriteString("room: " + yamlValue(cfg.Room) + "\n\n")
	b.WriteString("# Одноразовый код установки для привязки устройства к школе (T-07).\n")
	b.WriteString("# После регистрации не используется: device_id — в device.json, токен — в device_token.\n")
	b.WriteString("enroll_code: " + yamlValue(cfg.EnrollCode) + "\n\n")
	b.WriteString("# Папка состояния, журнала и очереди замеров (queue.db).\n")
	b.WriteString("data_dir: " + yamlValue(cfg.DataDir) + "\n\n")
	b.WriteString("# Уровень журнала: debug, info, warn, error.\n")
	b.WriteString("log_level: " + yamlValue(cfg.LogLevel) + "\n")
	return b.String()
}

// yamlValue quotes s the way YAML needs it — a Windows path with backslashes
// and a Russian room name must survive a round trip through ParseConfig.
func yamlValue(s string) string {
	data, err := yaml.Marshal(s)
	if err != nil {
		// yaml.Marshal of a string does not fail; quote defensively anyway.
		return strconv.Quote(s)
	}
	return strings.TrimRight(string(data), "\n")
}
