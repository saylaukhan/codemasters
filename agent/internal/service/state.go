package service

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// stateFileName is the file in DataDir that the running agent keeps up to
// date and `vko-agent status` reads.
const stateFileName = "state.json"

// State is what the running agent reports about itself to `vko-agent status`.
// The scheduler (T-08) sets LastMeasurementAt, the queue (T-11) sets QueueSize.
type State struct {
	Version           string     `json:"version"`
	StartedAt         time.Time  `json:"started_at"`
	LastMeasurementAt *time.Time `json:"last_measurement_at,omitempty"`
	QueueSize         int        `json:"queue_size"`
}

// StatePath returns the state file location inside dataDir.
func StatePath(dataDir string) string {
	return filepath.Join(dataDir, stateFileName)
}

// ReadState reads the state file. A missing file returns an error that
// satisfies errors.Is(err, os.ErrNotExist).
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

// WriteState replaces the state file atomically, so `status` never reads a
// half-written file.
func WriteState(dataDir string, st State) error {
	data, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	tmp := StatePath(dataDir) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, StatePath(dataDir))
}
