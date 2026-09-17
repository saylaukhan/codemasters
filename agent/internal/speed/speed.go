// Package speed measures Download and Upload against the measurement server
// (plan.md §4.3, step 4; ADR-012): LibreSpeed first, ndt7 when LibreSpeed
// does not answer.
//
// Server addresses come from GET /api/agent/config, never from the code.
// Values are raw: the status of the measurement is set by the server (ADR-004).
package speed

import (
	"context"
	"crypto/rand"
	"fmt"
	"log/slog"
	"sync"
	"time"
)

// Method is the engine that measured; it is written into the measurement.
type Method string

const (
	MethodLibreSpeed Method = "librespeed"
	MethodNDT7       Method = "ndt7"
)

// DefaultDuration is the length of one direction (ADR-012).
const DefaultDuration = 10 * time.Second

// Streams per direction, as in the LibreSpeed web client.
const (
	downloadStreams = 6
	uploadStreams   = 3
)

// Options configure Run.
type Options struct {
	// LibreSpeedURL is the main server, http(s)://host[:port].
	LibreSpeedURL string
	// NDT7URL is the fallback server, ws(s)://host[:port].
	NDT7URL string
	// Duration of one direction; DefaultDuration by default, tests shorten it.
	Duration time.Duration
	// Streams, when set, replaces the LibreSpeed stream count of both directions.
	Streams int
	Logger  *slog.Logger
}

// Result of a speed test.
type Result struct {
	Method Method
	// Server is the address of the server that measured, as configured.
	Server       string
	DownloadMbps float64
	UploadMbps   float64
	// DurationS is the whole test in seconds, a failed LibreSpeed attempt included.
	DurationS float64
	// Fallback is why LibreSpeed did not measure; empty when it did.
	Fallback string
}

// Run measures Download and then Upload with LibreSpeed; if LibreSpeed fails
// in either direction, both are measured again with ndt7, so the result
// always comes from one server. The error is returned when neither engine
// measured or ctx is cancelled.
func Run(ctx context.Context, opts Options) (Result, error) {
	if opts.Duration <= 0 {
		opts.Duration = DefaultDuration
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	start := time.Now()

	fallback := "адрес LibreSpeed не задан"
	if opts.LibreSpeedURL != "" {
		res, err := runLibreSpeed(ctx, opts)
		if ctx.Err() != nil {
			return Result{}, ctx.Err()
		}
		if err == nil {
			res.DurationS = time.Since(start).Seconds()
			return res, nil
		}
		fallback = "LibreSpeed: " + err.Error()
	}
	if opts.NDT7URL == "" {
		return Result{}, fmt.Errorf("%s; адрес ndt7 не задан", fallback)
	}
	opts.Logger.Warn("замер скорости через ndt7", "reason", fallback, "server", opts.NDT7URL)

	res, err := runNDT7(ctx, opts)
	if ctx.Err() != nil {
		return Result{}, ctx.Err()
	}
	if err != nil {
		return Result{}, fmt.Errorf("%s; ndt7: %w", fallback, err)
	}
	res.Fallback = fallback
	res.DurationS = time.Since(start).Seconds()
	return res, nil
}

// sample is what one direction transferred and for how long.
type sample struct {
	Bytes   int64
	Elapsed time.Duration
}

// mbps is the mean speed over the whole sample in megabits per second.
func (s sample) mbps() float64 {
	if s.Elapsed <= 0 {
		return 0
	}
	return float64(s.Bytes) * 8 / s.Elapsed.Seconds() / 1e6
}

// filler returns 1 MiB of random upload payload shared by all streams: the
// server throws it away, random bytes only keep it incompressible.
var filler = sync.OnceValue(func() []byte {
	b := make([]byte, 1<<20)
	_, _ = rand.Read(b)
	return b
})
