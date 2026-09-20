// Package update keeps the agent up to date by itself: it sees the version
// the server expects in the configuration (T-13), asks for the release of its
// channel, downloads the MSI, checks its SHA-256 and its signature, installs
// it through a separate updater process and rolls back to the previous
// version when the new one never reports itself (ТЗ п. 20, plan.md §4.6).
//
// Nothing here is built into the agent: the version, the channel and the file
// come from the server, and an administrator decides what is published
// (ADR-004).
package update

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// checkInterval is how often the loop looks at the configuration in memory.
// The version itself arrives from the server with the configuration
// (config_refresh_interval_s, T-13), so this check costs nothing and asks the
// server about a release only when the version there is a newer one.
const checkInterval = 15 * time.Minute

// confirmPoll is how often a pending update is looked at while it waits for
// the heartbeat of the new version: shorter than checkInterval, so a rollback
// starts soon after confirmDeadline.
const confirmPoll = time.Minute

// ErrNotSigned is a release without an Authenticode signature. Releases are
// not signed yet (agent-msi.yml has the signtool step commented out until the
// certificate of the department is there), so this alone does not stop an
// update: the SHA-256 the server sent over an authenticated connection is
// what the agent checks (docs/known-limitations.md).
var ErrNotSigned = errors.New("установщик не подписан")

// Options configure Run.
type Options struct {
	// DataDir holds update-state.json and the downloaded releases; required.
	DataDir string
	// ConfigPath is the config file of the agent, passed on to the updater
	// process: it needs the data directory for its msiexec logs.
	ConfigPath string
	// ServerURL is the base address for a relative download_url and the host
	// the device token may be sent to.
	ServerURL string
	// Client asks GET /api/agent/releases/latest; required.
	Client *api.Client
	// Version is the version running now (buildinfo.Version).
	Version string
	// LatestVersion is the version the server expects, read from the
	// configuration in memory (T-13); an empty string means it said nothing.
	LatestVersion func() string
	// LastHeartbeat is when the server last accepted a heartbeat, the zero
	// time until it did: an update confirms itself by one (T-12).
	LastHeartbeat func() time.Time
	// ExePath is the installed binary re-executed as the updater;
	// os.Executable by default.
	ExePath string
	Logger  *slog.Logger
	// Now is the clock, time.Now when nil; tests replace it.
	Now func() time.Time
	// launcher replaces the start of the updater process in the tests of this
	// package; nil starts the real one.
	launcher func(msi, version, remove string) error
}

// withDefaults fills what the caller left out and reports whether the options
// are usable at all.
func (o Options) withDefaults() (Options, error) {
	if o.Logger == nil {
		o.Logger = slog.Default()
	}
	if o.Now == nil {
		o.Now = time.Now
	}
	if o.LatestVersion == nil {
		o.LatestVersion = func() string { return "" }
	}
	if o.LastHeartbeat == nil {
		o.LastHeartbeat = func() time.Time { return time.Time{} }
	}
	if o.ExePath == "" {
		exe, err := os.Executable()
		if err != nil {
			return o, fmt.Errorf("путь к исполняемому файлу агента: %w", err)
		}
		o.ExePath = exe
	}
	if o.DataDir == "" || o.Client == nil {
		return o, errors.New("самообновление: не заданы папка данных или клиент API")
	}
	return o, nil
}

// Run keeps the agent up to date until ctx is done: it first settles the
// update that is already under way (confirm or roll back) and then installs
// the version the server expects. It never blocks anything else — the
// measurements, the queue and the heartbeat run in their own goroutines — and
// after a failure waits api.Backoff, like runConfig does.
func Run(ctx context.Context, opts Options) {
	o, err := opts.withDefaults()
	if err != nil {
		o.Logger.Error("самообновление не запущено", "err", err)
		return
	}
	if o.Version == DevVersion {
		// A local build is never replaced by a release: the developer would
		// silently lose the code the binary was built from.
		o.Logger.Info("самообновление выключено: агент собран локально", "version", o.Version)
		return
	}

	var backoff api.Backoff
	for {
		wait, done, err := o.once(ctx)
		if ctx.Err() != nil {
			return
		}
		switch {
		case err != nil:
			wait = backoff.Next(err)
			o.Logger.Warn("обновление не выполнено, повтор позже", "err", err, "retry_in", wait)
		case done:
			// msiexec is already running and it stops the service: there is
			// nothing left for this process to do.
			return
		default:
			backoff.Reset()
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(wait):
		}
	}
}

// once does one round: it settles the pending update when there is one, and
// otherwise looks for a newer version. done is true when the updater process
// is running and this process is about to be stopped by it.
func (o Options) once(ctx context.Context) (wait time.Duration, done bool, err error) {
	st, err := ReadState(o.DataDir)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		// A broken record is not a reason to stop updating: an update nobody
		// remembers cannot be rolled back anyway, and the next one replaces it.
		o.Logger.Warn("состояние обновления не прочитано, начинаем с чистого", "err", err)
		st = State{}
	}
	if st.Pending != nil {
		return o.resolve(st)
	}
	return o.check(ctx, st)
}

// resolve settles the pending update by Decide: it confirms the new version,
// rolls back to the previous one or writes the update off.
func (o Options) resolve(st State) (time.Duration, bool, error) {
	p := *st.Pending
	switch d := Decide(p, o.Version, o.LastHeartbeat(), o.Now()); d {
	case Wait:
		return confirmPoll, false, nil

	case Confirmed:
		o.Logger.Info("обновление подтверждено heartbeat новой версии",
			"version", p.ToVersion, "from", p.FromVersion)
		st.Pending = nil
		st.InstalledMSI = p.MSIPath
		if p.PreviousMSI != "" {
			// Nothing rolls back to it any more, and an MSI is tens of
			// megabytes on the disk of a school computer.
			remove(p.PreviousMSI)
		}
		// The updater has done its work and exited long ago.
		remove(o.updaterPath(p.ToVersion))
		return checkInterval, false, o.save(st)

	case Rollback:
		o.Logger.Error("новая версия не вышла на связь, откат на прежнюю",
			"version", p.ToVersion, "from", p.FromVersion, "started_at", p.StartedAt,
			"deadline", confirmDeadline, "msi", p.PreviousMSI)
		st.Pending = nil
		st.InstalledMSI = p.PreviousMSI
		st = st.markFailed(p.ToVersion)
		if err := o.save(st); err != nil {
			return checkInterval, false, err
		}
		// The package refuses to install over a newer version, so the rollback
		// removes the installation that is there now first (apply.go).
		if err := o.launch(p.PreviousMSI, p.FromVersion, p.MSIPath); err != nil {
			return checkInterval, false, err
		}
		return checkInterval, true, nil

	default: // GiveUp
		o.Logger.Error("обновление не состоялось, откат невозможен", "decision", d.String(),
			"version", p.ToVersion, "current", o.Version, "previous_msi", p.PreviousMSI)
		st.Pending = nil
		st = st.markFailed(p.ToVersion)
		return checkInterval, false, o.save(st)
	}
}

// check installs the version the server expects, when it is newer than the
// one running: the release of the channel, the file, its hash, its signature
// and then the updater process.
func (o Options) check(ctx context.Context, st State) (time.Duration, bool, error) {
	latest := o.LatestVersion()
	if latest == "" || !Newer(o.Version, latest) {
		return checkInterval, false, nil
	}
	if st.failed(latest) {
		o.Logger.Warn("версия уже не установилась на этом компьютере, повторная попытка не делается",
			"version", latest, "current", o.Version)
		return checkInterval, false, nil
	}

	rel, err := o.Client.GetLatestRelease(ctx)
	switch {
	case errors.Is(err, api.ErrNoRelease):
		o.Logger.Warn("сервер ждёт новую версию, но релиза на канале нет", "latest_version", latest)
		return checkInterval, false, nil
	case err != nil:
		return 0, false, fmt.Errorf("релиз не получен: %w", err)
	}
	if err := rel.Validate(); err != nil {
		return 0, false, err
	}
	if !Newer(o.Version, rel.Version) {
		o.Logger.Warn("релиз канала не новее установленной версии",
			"release", rel.Version, "channel", rel.Channel, "current", o.Version)
		return checkInterval, false, nil
	}
	if st.failed(rel.Version) {
		o.Logger.Warn("релиз уже не установился на этом компьютере, повторная попытка не делается",
			"version", rel.Version)
		return checkInterval, false, nil
	}
	o.Logger.Info("найдено обновление агента", "version", rel.Version, "channel", rel.Channel,
		"current", o.Version, "released_at", rel.ReleasedAt)

	path, err := download(ctx, o, rel)
	if err != nil {
		return 0, false, err
	}
	if err := Verify(path, rel.SHA256); err != nil {
		// A release whose hash does not match is refused for good: the file is
		// deleted and the version is not downloaded again until the server
		// publishes another one (ТЗ п. 20).
		o.Logger.Error("обновление отклонено: sha256 не совпал", "version", rel.Version,
			"want_sha256", rel.SHA256, "err", err)
		return checkInterval, false, o.save(st.markFailed(rel.Version))
	}
	if err := verifySignature(path); err != nil {
		if !errors.Is(err, ErrNotSigned) {
			remove(path)
			o.Logger.Error("обновление отклонено: подпись установщика не прошла проверку",
				"version", rel.Version, "err", err)
			return checkInterval, false, o.save(st.markFailed(rel.Version))
		}
		o.Logger.Warn("установщик без подписи, установка по совпавшему sha256",
			"version", rel.Version, "err", err)
	}

	if st.InstalledMSI == "" {
		// The agent was installed by hand or by the MSI of another folder: the
		// file of the current version is unknown, so this update cannot be
		// rolled back (docs/known-limitations.md).
		o.Logger.Warn("установщик прежней версии неизвестен: откат этого обновления будет невозможен",
			"current", o.Version)
	}
	st.Pending = &Pending{
		FromVersion: o.Version,
		ToVersion:   rel.Version,
		MSIPath:     path,
		PreviousMSI: st.InstalledMSI,
		StartedAt:   o.Now(),
	}
	if err := o.save(st); err != nil {
		return 0, false, err
	}
	// A failed launch leaves the record: the previous version keeps running,
	// and after confirmDeadline Decide writes the update off (GiveUp).
	if err := o.launch(path, rel.Version, ""); err != nil {
		return 0, false, err
	}
	o.Logger.Info("установка обновления запущена", "version", rel.Version, "msi", path,
		"deadline", confirmDeadline)
	return checkInterval, true, nil
}

// save writes the update record; a failure is an error of the round, because
// without the record the new version has nothing to confirm or roll back.
func (o Options) save(st State) error {
	if err := WriteState(o.DataDir, st); err != nil {
		return fmt.Errorf("запись состояния обновления: %w", err)
	}
	return nil
}
