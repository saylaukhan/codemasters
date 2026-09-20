package update

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// installTimeout is not set on purpose: msiexec stops the service, replaces
// the files and starts the service again, and on a slow computer that takes
// minutes. The updater process is killed by nothing, so it waits as long as
// msiexec needs.

// launch starts the separate updater process and returns at once. It must be
// separate: msiexec stops the service VKOMonitorAgent, and a child process of
// that service would be stopped together with it before it installed
// anything (plan.md §4.6).
//
// remove, when set, is the MSI of the installation to uninstall first; a
// rollback needs it, because the package refuses to install over a newer
// version (installer/wix/Package.wxs, MajorUpgrade).
func (o Options) launch(msi, version, remove string) error {
	if o.launcher != nil {
		// The tests of this package replace the launch: `make check` must not
		// start msiexec on the computer of a developer.
		return o.launcher(msi, version, remove)
	}
	exe, err := o.updaterCopy(version)
	if err != nil {
		return err
	}
	args := []string{"update-apply", "--config", o.ConfigPath, "--msi", msi, "--version", version}
	if remove != "" {
		args = append(args, "--remove", remove)
	}
	cmd := exec.Command(exe, args...)
	detach(cmd)
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("запуск установщика обновления: %w", err)
	}
	o.Logger.Info("установщик обновления запущен", "pid", cmd.Process.Pid, "version", version,
		"msi", msi, "exe", exe)
	// Nothing waits for it: this process is about to be stopped by msiexec.
	return cmd.Process.Release()
}

// updaterPath is the copy of the agent binary that installs version.
func (o Options) updaterPath(version string) string {
	return filepath.Join(UpdatesDir(o.DataDir), "updater-"+version+filepath.Ext(o.ExePath))
}

// updaterCopy copies the agent binary beside the downloaded releases and
// returns the copy. The updater may not run from the file the installation
// replaces: Windows cannot overwrite the image of a running process, and
// msiexec would postpone the replacement to the next reboot instead of
// finishing the update (plan.md §4.6).
func (o Options) updaterCopy(version string) (string, error) {
	src, err := os.Open(o.ExePath)
	if err != nil {
		return "", fmt.Errorf("копия агента для обновления: %w", err)
	}
	defer src.Close()

	path := o.updaterPath(version)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	if _, err := writeFile(path, src); err != nil {
		remove(path)
		return "", fmt.Errorf("копия агента для обновления: %w", err)
	}
	// The copy is started as a process: outside Windows it needs the x bit.
	if err := os.Chmod(path, 0o755); err != nil {
		return "", err
	}
	return path, nil
}

// InstallOptions configure Install.
type InstallOptions struct {
	// DataDir holds the msiexec logs, next to the downloaded releases.
	DataDir string
	// MSI is the installer to install; required.
	MSI string
	// Version is what is being installed; it names the log files.
	Version string
	// Remove is the MSI of the installation to uninstall first (a rollback).
	Remove string
	Logger *slog.Logger
}

// Install is the work of the updater process (`vko-agent update-apply`): an
// uninstall of Remove when a rollback asked for one, then a silent install of
// MSI with a verbose log in DataDir/updates. It blocks until msiexec is done,
// so the log of the agent keeps its result.
func Install(ctx context.Context, opts InstallOptions) error {
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	if opts.MSI == "" {
		return errors.New("установка обновления: не указан файл MSI")
	}
	if runtime.GOOS != "windows" {
		// The release of the agent is an MSI (installer/wix): elsewhere the
		// agent is updated by the package manager of the distribution.
		return errors.New("установка обновления возможна только на Windows: релиз агента — MSI")
	}
	if err := os.MkdirAll(UpdatesDir(opts.DataDir), 0o755); err != nil {
		return err
	}
	if opts.Remove != "" {
		if err := msiexec(ctx, opts, "/x", opts.Remove, "remove"); err != nil {
			return fmt.Errorf("удаление прежней установки: %w", err)
		}
	}
	return msiexec(ctx, opts, "/i", opts.MSI, "install")
}

// msiexec runs one silent msiexec action and keeps its verbose log beside the
// releases: without it a failed installation on a school computer cannot be
// explained afterwards.
func msiexec(ctx context.Context, opts InstallOptions, action, msi, step string) error {
	logPath := filepath.Join(UpdatesDir(opts.DataDir), fmt.Sprintf("msiexec-%s-%s.log", opts.Version, step))
	args := []string{action, msi, "/qn", "/norestart", "/l*v", logPath}
	opts.Logger.Info("msiexec запускается", "args", args)
	out, err := exec.CommandContext(ctx, "msiexec", args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("msiexec %s %s: %w (%s; журнал %s)", action, msi, err, strings.TrimSpace(string(out)), logPath)
	}
	opts.Logger.Info("msiexec отработал", "action", action, "msi", msi, "log", logPath)
	return nil
}
