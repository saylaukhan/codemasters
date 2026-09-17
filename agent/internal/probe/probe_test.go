package probe

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"math"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestSeriesStats(t *testing.T) {
	const eps = 1e-9
	msec := func(v ...int) []time.Duration {
		out := make([]time.Duration, len(v))
		for i, x := range v {
			out[i] = time.Duration(x) * time.Millisecond
		}
		return out
	}
	tests := []struct {
		name   string
		series Series
		want   Stats
	}{
		{
			name:   "odd count, no loss",
			series: Series{RTTs: msec(10, 30, 20), Sent: 3},
			// sorted 10 20 30; |30-10| + |20-30| = 30 over 2 pairs
			want: Stats{PingMs: 20, JitterMs: 15, LossPct: 0, Sent: 3, Received: 3},
		},
		{
			name:   "even count with loss",
			series: Series{RTTs: msec(10, 20, 15, 40), Sent: 5},
			// sorted 10 15 20 40 → (15+20)/2; |10|+|5|+|25| = 40 over 3 pairs; 1 of 5 lost
			want: Stats{PingMs: 17.5, JitterMs: 40.0 / 3, LossPct: 20, Sent: 5, Received: 4},
		},
		{
			name:   "one answer",
			series: Series{RTTs: msec(42), Sent: 30},
			want:   Stats{PingMs: 42, JitterMs: 0, LossPct: 29.0 / 30 * 100, Sent: 30, Received: 1},
		},
		{
			name:   "no answers",
			series: Series{Sent: 30},
			want:   Stats{LossPct: 100, Sent: 30},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.series.Stats()
			if math.Abs(got.PingMs-tt.want.PingMs) > eps || math.Abs(got.JitterMs-tt.want.JitterMs) > eps ||
				math.Abs(got.LossPct-tt.want.LossPct) > eps || got.Sent != tt.want.Sent ||
				got.Received != tt.want.Received {
				t.Fatalf("Stats() = %+v, want %+v", got, tt.want)
			}
		})
	}
}

func newServer(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)
	return srv
}

func quiet() *slog.Logger { return slog.New(slog.NewTextHandler(io.Discard, nil)) }

func stubICMP(t *testing.T, fn func(ctx context.Context, host string, count int, interval time.Duration) (Series, error)) {
	t.Helper()
	orig := icmpSeries
	icmpSeries = fn
	t.Cleanup(func() { icmpSeries = orig })
}

func TestRunUsesICMP(t *testing.T) {
	stubICMP(t, func(_ context.Context, host string, count int, _ time.Duration) (Series, error) {
		if host != "127.0.0.1" || count != 3 {
			t.Errorf("icmp to %s x%d, want 127.0.0.1 x3", host, count)
		}
		return Series{RTTs: []time.Duration{time.Millisecond, 3 * time.Millisecond}, Sent: 3}, nil
	})
	srv := newServer(t)
	res, err := Run(context.Background(), Options{ServerURL: srv.URL, TargetURL: srv.URL, Count: 3, Logger: quiet()})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if res.Status != Online || res.Method != MethodICMP || res.PingMs != 2 || res.Received != 2 {
		t.Fatalf("Run = %+v, want online icmp with ping 2 ms and 2 answers", res)
	}
}

func TestRunFallsBackToTCP(t *testing.T) {
	for name, icmp := range map[string]func(context.Context, string, int, time.Duration) (Series, error){
		"socket not permitted": func(context.Context, string, int, time.Duration) (Series, error) {
			return Series{}, errors.New("socket: operation not permitted")
		},
		"no icmp answers": func(_ context.Context, _ string, count int, _ time.Duration) (Series, error) {
			return Series{Sent: count}, nil
		},
	} {
		t.Run(name, func(t *testing.T) {
			stubICMP(t, icmp)
			srv := newServer(t)
			opts := Options{ServerURL: srv.URL, TargetURL: srv.URL, Count: 3, Interval: 5 * time.Millisecond, Logger: quiet()}
			res, err := Run(context.Background(), opts)
			if err != nil {
				t.Fatalf("Run: %v", err)
			}
			if res.Status != Online || res.Method != MethodTCP || res.Sent != 3 || res.Received != 3 || res.LossPct != 0 {
				t.Fatalf("Run = %+v, want online tcp with 3 of 3 answers", res)
			}
		})
	}
}

func TestRunOffline(t *testing.T) {
	srv := newServer(t)
	srv.Close() // nothing listens on the port any more
	res, err := Run(context.Background(), Options{ServerURL: srv.URL, TargetURL: srv.URL, Logger: quiet()})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if res.Status != Offline || res.Reason == "" || res.Method != "" || res.Sent != 0 {
		t.Fatalf("Run = %+v, want offline with a reason and no series", res)
	}
}

// TestRunLocalServer sends a real series to the local server: ICMP where the
// OS allows it, TCP-connect otherwise.
func TestRunLocalServer(t *testing.T) {
	srv := newServer(t)
	opts := Options{ServerURL: srv.URL, TargetURL: srv.URL, Count: 3, Interval: 10 * time.Millisecond, Logger: quiet()}
	res, err := Run(context.Background(), opts)
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if res.Status != Online || (res.Method != MethodICMP && res.Method != MethodTCP) || res.Received == 0 {
		t.Fatalf("Run = %+v, want online with answers", res)
	}
	t.Logf("method %s, ping %.3f ms, jitter %.3f ms, loss %.0f%%", res.Method, res.PingMs, res.JitterMs, res.LossPct)
}

func TestRunRejectsBadTarget(t *testing.T) {
	if _, err := Run(context.Background(), Options{ServerURL: "http://localhost", TargetURL: "speedtest"}); err == nil {
		t.Fatal("Run with target without scheme: want error")
	}
}
