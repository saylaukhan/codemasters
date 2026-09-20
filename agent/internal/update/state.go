package update

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// stateFileName is the record in DataDir that outlives the update itself: the
// version that starts after msiexec reads from it what it must confirm or
// roll back (T-50).
const stateFileName = "update-state.json"

// confirmDeadline is how long the new version has to make the server accept a
// heartbeat. The default heartbeat is 5 minutes (service.DefaultHeartbeatInterval),
// so this is three of them in a row: enough for a slow service start and a
// school line that comes up after the computer, short enough to roll a broken
// release back the same day.
const confirmDeadline = 15 * time.Minute

// State is DataDir/update-state.json.
type State struct {
	// InstalledMSI is the file the version running now was installed from; it
	// is kept so a failed update has something to roll back to. It is empty
	// after an installation by hand: the first self-update cannot roll back
	// (docs/known-limitations.md).
	InstalledMSI string `json:"installed_msi,omitempty"`
	// Pending is the update being installed; nil when there is none.
	Pending *Pending `json:"pending,omitempty"`
	// Failed lists the versions that did not confirm themselves. They are not
	// downloaded again, so a broken release cannot put a computer into an
	// endless install-and-roll-back loop.
	Failed []string `json:"failed,omitempty"`
}

// Pending is the update the agent started and has not confirmed yet.
type Pending struct {
	FromVersion string `json:"from_version"`
	ToVersion   string `json:"to_version"`
	// MSIPath is the file of ToVersion; a rollback uninstalls it.
	MSIPath string `json:"msi_path"`
	// PreviousMSI is the file of FromVersion, empty when it is not known.
	PreviousMSI string `json:"previous_msi,omitempty"`
	// StartedAt is when the updater process was launched (ADR-014).
	StartedAt time.Time `json:"started_at"`
}

// failed reports whether version already failed to install on this computer.
func (s State) failed(version string) bool {
	for _, v := range s.Failed {
		if v == version {
			return true
		}
	}
	return false
}

// markFailed remembers that version did not confirm itself.
func (s State) markFailed(version string) State {
	if !s.failed(version) {
		s.Failed = append(s.Failed, version)
	}
	return s
}

// StatePath returns the update record inside dataDir.
func StatePath(dataDir string) string {
	return filepath.Join(dataDir, stateFileName)
}

// ReadState reads the update record. A missing file returns the zero state
// and an error that satisfies errors.Is(err, os.ErrNotExist).
func ReadState(dataDir string) (State, error) {
	data, err := os.ReadFile(StatePath(dataDir))
	if err != nil {
		return State{}, err
	}
	var st State
	if err := json.Unmarshal(data, &st); err != nil {
		return State{}, fmt.Errorf("разбор %s: %w", StatePath(dataDir), err)
	}
	return st, nil
}

// WriteState replaces the update record atomically, like the configuration
// cache: msiexec stops the service at any moment, and a half-written record
// would leave the new version with nothing to confirm.
func WriteState(dataDir string, st State) error {
	data, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		return err
	}
	tmp := StatePath(dataDir) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, StatePath(dataDir))
}

// Decision is what to do with a pending update.
type Decision int

const (
	// Wait: the deadline has not passed, the new version may still report itself.
	Wait Decision = iota
	// Confirmed: the new version runs and the server accepted its heartbeat.
	Confirmed
	// Rollback: reinstall the previous version.
	Rollback
	// GiveUp: there is nothing to roll back — the update did not take effect
	// at all, or the file of the previous version is not known.
	GiveUp
)

func (d Decision) String() string {
	switch d {
	case Wait:
		return "ожидание"
	case Confirmed:
		return "подтверждено"
	case Rollback:
		return "откат"
	default:
		return "отказ"
	}
}

// Decide tells what to do with the pending update p. current is the version
// running now (buildinfo.Version), lastHeartbeat is when the server last
// accepted a heartbeat (the zero time when it never did), now is the clock.
//
// It touches neither the disk nor the network, so the rule of the rollback is
// checked by tests alone (T-50).
func Decide(p Pending, current string, lastHeartbeat, now time.Time) Decision {
	updated := current == p.ToVersion
	if updated && lastHeartbeat.After(p.StartedAt) {
		return Confirmed
	}
	if now.Sub(p.StartedAt) < confirmDeadline {
		return Wait
	}
	switch {
	case !updated && current == p.FromVersion:
		// The installation did not take: the previous version is running, so
		// there is nothing to roll back — the update is written off.
		return GiveUp
	case p.PreviousMSI == "":
		// The agent was installed by hand and its MSI is not on the computer:
		// a rollback has nothing to install (docs/known-limitations.md).
		return GiveUp
	default:
		// The new version runs but the server has not heard it, or a version
		// nobody expected is running: back to the previous one.
		return Rollback
	}
}
