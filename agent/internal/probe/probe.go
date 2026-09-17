// Package probe checks the connection and measures ping, jitter and packet
// loss to the measurement server (plan.md §4.3, steps 1 and 3; ADR-012).
//
// Values are raw: the status of the measurement is set by the server (ADR-004).
package probe

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"runtime"
	"strings"
	"time"

	probing "github.com/prometheus-community/pro-bing"
)

// ConnectionStatus is connection_status of a measurement.
type ConnectionStatus string

const (
	Online  ConnectionStatus = "online"
	Offline ConnectionStatus = "offline"
)

// Method is how the ping series was sent; it is written into the measurement.
type Method string

const (
	MethodICMP Method = "icmp"
	MethodTCP  Method = "tcp"
)

// A series is 30 probes 200 ms apart (ADR-012).
const (
	DefaultCount    = 30
	DefaultInterval = 200 * time.Millisecond
)

// replyTimeout is how long a probe waits for its answer before it counts as lost.
const replyTimeout = 2 * time.Second

// checkTimeout bounds the connectivity check.
const checkTimeout = 10 * time.Second

// Options configure Run.
type Options struct {
	// ServerURL is the monitoring API (config server_url): the connectivity check goes there.
	ServerURL string
	// TargetURL is the measurement server from GET /api/agent/config; the series goes to its host.
	TargetURL string
	// Count and Interval default to DefaultCount and DefaultInterval; tests shorten them.
	Count    int
	Interval time.Duration
	Logger   *slog.Logger
}

// Result of one probe. When Status is Offline only Reason is set.
type Result struct {
	Status ConnectionStatus
	// Reason is why the connection check failed.
	Reason string
	Method Method
	// Host is the measurement server host the series went to.
	Host string
	Stats
}

// icmpSeries sends the ICMP series; tests replace it to simulate a blocked ICMP.
var icmpSeries = pingICMP

// Run checks the connection and, if it is up, sends the ping series: ICMP
// first, TCP-connect to the server port when ICMP fails or gets no answer.
// A lost connection is a result, not an error: the error is returned only for
// invalid options or a cancelled ctx.
func Run(ctx context.Context, opts Options) (Result, error) {
	if opts.Count <= 0 {
		opts.Count = DefaultCount
	}
	if opts.Interval <= 0 {
		opts.Interval = DefaultInterval
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	host, port, err := hostPort(opts.TargetURL)
	if err != nil {
		return Result{}, err
	}

	if err := checkConnection(ctx, opts.ServerURL); err != nil {
		if ctx.Err() != nil {
			return Result{}, ctx.Err()
		}
		opts.Logger.Warn("нет связи с сервером", "err", err)
		return Result{Status: Offline, Reason: err.Error()}, nil
	}

	series, err := icmpSeries(ctx, host, opts.Count, opts.Interval)
	if ctx.Err() != nil {
		return Result{}, ctx.Err()
	}
	if err == nil && len(series.RTTs) > 0 {
		return Result{Status: Online, Method: MethodICMP, Host: host, Stats: series.Stats()}, nil
	}
	if err == nil {
		err = errors.New("нет ответов на ICMP")
	}
	opts.Logger.Info("ICMP недоступен, серия через TCP-connect", "host", host, "port", port, "err", err)

	series = pingTCP(ctx, net.JoinHostPort(host, port), opts.Count, opts.Interval)
	if ctx.Err() != nil {
		return Result{}, ctx.Err()
	}
	return Result{Status: Online, Method: MethodTCP, Host: host, Stats: series.Stats()}, nil
}

// checkConnection resolves the server name and sends an HTTP request to the
// server. Any HTTP answer means the line works: a 5xx of the API is a server
// problem, not a lost connection of the school.
func checkConnection(ctx context.Context, serverURL string) error {
	host, _, err := hostPort(serverURL)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(ctx, checkTimeout)
	defer cancel()

	if net.ParseIP(host) == nil {
		if _, err := net.DefaultResolver.LookupHost(ctx, host); err != nil {
			return fmt.Errorf("DNS %s: %w", host, err)
		}
	}
	healthURL := strings.TrimRight(serverURL, "/") + "/api/health"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL, nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("HTTP: %w", err)
	}
	return resp.Body.Close()
}

// pingICMP sends the series with pro-bing and orders the answers by sequence.
func pingICMP(ctx context.Context, host string, count int, interval time.Duration) (Series, error) {
	p, err := probing.NewPinger(host)
	if err != nil {
		return Series{}, err
	}
	p.Count = count
	p.Interval = interval
	p.Timeout = time.Duration(count)*interval + replyTimeout
	// Windows and root on Linux need a raw socket; elsewhere a datagram ICMP
	// socket works without privileges (macOS, Linux with ping_group_range).
	p.SetPrivileged(runtime.GOOS == "windows" || os.Geteuid() == 0)
	rtts := make([]time.Duration, count)
	answered := make([]bool, count)
	p.OnRecv = func(pkt *probing.Packet) {
		if pkt.Seq >= 0 && pkt.Seq < count {
			rtts[pkt.Seq], answered[pkt.Seq] = pkt.Rtt, true
		}
	}
	if err := p.RunWithContext(ctx); err != nil {
		return Series{}, err
	}

	s := Series{Sent: p.Statistics().PacketsSent}
	for i, ok := range answered {
		if ok {
			s.RTTs = append(s.RTTs, rtts[i])
		}
	}
	return s, nil
}

// pingTCP opens and closes a TCP connection to addr count times; the connect
// time is the RTT, a failed connect is a lost probe.
func pingTCP(ctx context.Context, addr string, count int, interval time.Duration) Series {
	d := net.Dialer{Timeout: replyTimeout}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	var s Series
	for i := range count {
		if i > 0 {
			select {
			case <-ctx.Done():
				return s
			case <-ticker.C:
			}
		}
		start := time.Now()
		conn, err := d.DialContext(ctx, "tcp", addr)
		s.Sent++
		if err != nil {
			continue
		}
		s.RTTs = append(s.RTTs, time.Since(start))
		_ = conn.Close()
	}
	return s
}

// hostPort returns the host and the port of an http(s) URL.
func hostPort(rawURL string) (host, port string, err error) {
	u, err := url.Parse(rawURL)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return "", "", fmt.Errorf("адрес %q должен быть http(s)://хост", rawURL)
	}
	port = u.Port()
	if port == "" {
		port = "80"
		if u.Scheme == "https" {
			port = "443"
		}
	}
	return u.Hostname(), port, nil
}
