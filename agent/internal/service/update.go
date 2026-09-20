package service

import (
	"context"
	"log/slog"
	"sync/atomic"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/update"
)

// beatClock remembers when the server last accepted a heartbeat. The
// heartbeat loop writes it, the self-update goroutine reads it: an update
// confirms itself by a heartbeat that carries the new version (T-12, T-50).
type beatClock struct {
	nano atomic.Int64
}

// mark records an accepted heartbeat.
func (b *beatClock) mark(at time.Time) { b.nano.Store(at.UnixNano()) }

// last is the zero time until the server accepted the first heartbeat.
func (b *beatClock) last() time.Time {
	nano := b.nano.Load()
	if nano == 0 {
		return time.Time{}
	}
	return time.Unix(0, nano)
}

// startUpdates starts the self-update in the background: it settles an update
// that is already under way (confirm or roll back) and installs the version
// the server expects (ТЗ п. 20, plan.md §4.6). configPath goes to the updater
// process, which needs the data directory for its logs.
func startUpdates(ctx context.Context, cfg Config, configPath string, client *api.Client,
	settings *Settings, beats *beatClock, logger *slog.Logger,
) {
	go update.Run(ctx, update.Options{
		DataDir:    cfg.DataDir,
		ConfigPath: configPath,
		ServerURL:  cfg.ServerURL,
		Client:     client,
		Version:    buildinfo.Version,
		// The version the server expects arrives with the configuration and
		// changes without a restart (T-13); empty means it said nothing.
		LatestVersion: func() string { return settings.Current().LatestVersion },
		LastHeartbeat: beats.last,
		Logger:        logger,
	})
}
