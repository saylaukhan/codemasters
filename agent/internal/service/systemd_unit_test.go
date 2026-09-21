//go:build !windows

package service

import (
	"bufio"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// unitPath is the systemd unit the Linux package installs (T-52). It is not
// generated from the Go code — kardianos/service writes its own unit for
// `vko-agent install` — so the two must be kept in step by hand, and these
// tests are what notices when they are not: a unit named differently from
// service.Name makes `vko-agent status` report «не установлена» on a host
// where the service is running.
const unitPath = "../../installer/linux/systemd/vko-agent.service"

// unitDirectives reads the unit as "section.Key" -> value. A directive that
// repeats (systemd allows it) keeps the last value, as systemd does.
func unitDirectives(t *testing.T) map[string]string {
	t.Helper()
	f, err := os.Open(unitPath)
	if err != nil {
		t.Fatalf("unit пакета: %v", err)
	}
	defer f.Close()

	out := map[string]string{}
	section := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = strings.Trim(line, "[]")
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			t.Fatalf("строка unit'а без «=»: %q", line)
		}
		out[section+"."+strings.TrimSpace(key)] = strings.TrimSpace(value)
	}
	if err := sc.Err(); err != nil {
		t.Fatalf("чтение unit'а: %v", err)
	}
	return out
}

func TestUnitFileNameMatchesServiceName(t *testing.T) {
	want := Name + ".service"
	if got := filepath.Base(unitPath); got != want {
		t.Errorf("имя файла unit'а = %q, а kardianos/service ищет %q (service.Name)", got, want)
	}
}

func TestUnitRunsAgentWithDefaultConfig(t *testing.T) {
	d := unitDirectives(t)

	wantExec := "/usr/bin/vko-agent run --config " + DefaultConfigPath()
	if got := d["Service.ExecStart"]; got != wantExec {
		t.Errorf("ExecStart = %q, want %q (service.DefaultConfigPath)", got, wantExec)
	}
	// Без StateDirectory systemd не создаст папку данных и не отдаст её службе.
	wantState := filepath.Base(DefaultDataDir())
	if got := d["Service.StateDirectory"]; got != wantState {
		t.Errorf("StateDirectory = %q, want %q (service.DefaultDataDir)", got, wantState)
	}
	if got := filepath.Join("/var/lib", d["Service.StateDirectory"]); got != DefaultDataDir() {
		t.Errorf("StateDirectory даёт папку %q, а агент пишет в %q", got, DefaultDataDir())
	}
}

func TestUnitRunsAsPackageUser(t *testing.T) {
	d := unitDirectives(t)

	// Строка «unit работает от root» в docs/known-limitations.md закрыта именно этим.
	for _, key := range []string{"Service.User", "Service.Group"} {
		if got := d[key]; got != UnitUserName {
			t.Errorf("%s = %q, want %q (service.UnitUserName, его заводит postinstall)", key, got, UnitUserName)
		}
	}
	// То же, что Option "Restart" в definition(): поведение службы не должно
	// зависеть от того, пакетом её поставили или `vko-agent install`.
	if got := d["Service.Restart"]; got != "on-failure" {
		t.Errorf("Restart = %q, want %q", got, "on-failure")
	}
	if got := d["Install.WantedBy"]; got != "multi-user.target" {
		t.Errorf("WantedBy = %q, want %q — иначе служба не стартует при загрузке", got, "multi-user.target")
	}
	if got := d["Unit.Description"]; !strings.Contains(got, DisplayName) {
		t.Errorf("Description = %q, want подстроку %q", got, DisplayName)
	}
}

// TestPackageScriptsUseSamePaths guards the paths the maintainer scripts hard-code:
// they create and chown exactly the directories the agent reads and writes.
func TestPackageScriptsUseSamePaths(t *testing.T) {
	data, err := os.ReadFile("../../installer/linux/scripts/postinstall.sh")
	if err != nil {
		t.Fatalf("postinstall пакета: %v", err)
	}
	script := string(data)
	for _, want := range []string{
		"CONFIG=" + DefaultConfigPath(),
		"DATA_DIR=" + DefaultDataDir(),
		"USER_NAME=" + UnitUserName,
		"SERVICE=" + Name + ".service",
	} {
		if !strings.Contains(script, want) {
			t.Errorf("postinstall.sh не содержит %q — пути пакета разошлись с агентом", want)
		}
	}
}
