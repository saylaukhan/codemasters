package service

import (
	"context"
	"crypto/rand"
	"fmt"
	"log/slog"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
	"github.com/saylaukhan/codemasters/agent/internal/netinfo"
	"github.com/saylaukhan/codemasters/agent/internal/probe"
	"github.com/saylaukhan/codemasters/agent/internal/speed"
)

// MeasureOptions configure Measure. The measurement server addresses come
// from GET /api/agent/config (T-13), never from the code (ADR-012).
type MeasureOptions struct {
	// ServerURL is the monitoring API: the connectivity check goes there.
	ServerURL string
	// TargetURL is the measurement server the ping series goes to; ServerURL when empty.
	TargetURL string
	// LibreSpeedURL and NDT7URL are the speed test servers; both empty skips the speed test.
	LibreSpeedURL string
	NDT7URL       string
	// Client asks the server for the external IP; nil skips it.
	Client *api.Client
	Logger *slog.Logger
}

// Measure takes one measurement (plan.md §4.3): connectivity, ping series,
// adapter, external IP and speed. No connection is a measurement too, with
// connection_status offline (ТЗ п. 2). A failed step leaves its values empty;
// the error is returned only when ctx is cancelled or the options are invalid.
func Measure(ctx context.Context, opts MeasureOptions) (api.Measurement, error) {
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	if opts.TargetURL == "" {
		opts.TargetURL = opts.ServerURL
	}
	id, err := newMeasurementUUID()
	if err != nil {
		return api.Measurement{}, err
	}
	m := api.Measurement{
		MeasurementUUID: id,
		MeasuredAt:      time.Now(),
		AgentVersion:    buildinfo.Version,
	}

	res, err := probe.Run(ctx, probe.Options{ServerURL: opts.ServerURL, TargetURL: opts.TargetURL, Logger: opts.Logger})
	if err != nil {
		return api.Measurement{}, err
	}
	m.ConnectionStatus = string(res.Status)
	if res.Status == probe.Offline {
		opts.Logger.Warn("нет связи: замер записан как offline", "reason", res.Reason)
		return m, nil
	}
	m.PacketLossPct = &res.LossPct
	if res.Received > 0 {
		m.PingMs, m.JitterMs = &res.PingMs, &res.JitterMs
	}
	if info, err := netinfo.Detect(res.Host); err == nil {
		m.IfaceType = string(info.Type)
	} else {
		opts.Logger.Warn("адаптер не определён", "err", err)
	}
	if opts.Client != nil {
		if ip, err := opts.Client.WhoAmI(ctx); err == nil {
			m.ExternalIP = ip
		} else {
			opts.Logger.Warn("внешний IP не получен", "err", err)
		}
	}

	if opts.LibreSpeedURL == "" && opts.NDT7URL == "" {
		return m, nil
	}
	sp, err := speed.Run(ctx, speed.Options{LibreSpeedURL: opts.LibreSpeedURL, NDT7URL: opts.NDT7URL, Logger: opts.Logger})
	if err != nil {
		if ctx.Err() != nil {
			return api.Measurement{}, ctx.Err()
		}
		opts.Logger.Warn("замер скорости не удался", "err", err)
		return m, nil
	}
	m.DownloadMbps, m.UploadMbps, m.DurationS = &sp.DownloadMbps, &sp.UploadMbps, &sp.DurationS
	m.Server = fmt.Sprintf("%s %s", sp.Method, sp.Server)
	return m, nil
}

// newMeasurementUUID returns a random UUID version 4, the idempotency key of a measurement (ADR-006).
func newMeasurementUUID() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	b[6] = b[6]&0x0f | 0x40
	b[8] = b[8]&0x3f | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:]), nil
}
