package speed

import (
	"bufio"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func quiet() *slog.Logger { return slog.New(slog.NewTextHandler(io.Discard, nil)) }

func TestSampleMbps(t *testing.T) {
	tests := []struct {
		name string
		s    sample
		want float64
	}{
		{"1 Mbit/s", sample{Bytes: 125_000, Elapsed: time.Second}, 1},
		{"100 MB in 10 s", sample{Bytes: 100_000_000, Elapsed: 10 * time.Second}, 80},
		{"1 MiB in half a second", sample{Bytes: 1 << 20, Elapsed: 500 * time.Millisecond}, 16.777216},
		{"no time", sample{Bytes: 1 << 20}, 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.s.mbps(); math.Abs(got-tt.want) > 1e-9 {
				t.Fatalf("mbps() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestRunStreams(t *testing.T) {
	const d = 50 * time.Millisecond
	// move adds 1000 bytes once and holds the request until the time is up.
	move := func(ctx context.Context, n *atomic.Int64) error {
		n.Add(1000)
		<-ctx.Done()
		return ctx.Err()
	}
	tests := []struct {
		name      string
		failFirst int // how many of the 3 streams fail at once
		request   func(context.Context, *atomic.Int64) error
		wantBytes int64
		wantErr   bool
	}{
		{name: "all streams move data", request: move, wantBytes: 3000},
		{name: "one stream fails", failFirst: 1, request: move, wantBytes: 2000},
		{name: "every stream fails", failFirst: 3, request: move, wantErr: true},
		{name: "nothing moved", request: func(ctx context.Context, _ *atomic.Int64) error {
			<-ctx.Done()
			return ctx.Err()
		}, wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var calls atomic.Int64
			s, err := runStreams(context.Background(), 3, d, func(ctx context.Context, n *atomic.Int64) error {
				if calls.Add(1) <= int64(tt.failFirst) {
					return errors.New("HTTP 502")
				}
				return tt.request(ctx, n)
			})
			if tt.wantErr {
				if err == nil {
					t.Fatalf("runStreams = %+v, want error", s)
				}
				return
			}
			if err != nil || s.Bytes != tt.wantBytes || s.Elapsed < d {
				t.Fatalf("runStreams = %+v, %v; want %d bytes over at least %v", s, err, tt.wantBytes, d)
			}
		})
	}
}

// libreSpeedServer is a fake LibreSpeed: a download response is 1 MiB and then
// hangs until the client leaves; upload bytes are counted as they arrive.
func libreSpeedServer(t *testing.T, uploaded *atomic.Int64) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/backend/garbage.php":
			_, _ = w.Write(filler())
			_ = http.NewResponseController(w).Flush()
			<-r.Context().Done()
		case "/backend/empty.php":
			_, _ = io.Copy(counter{uploaded}, r.Body)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestLibreDownloadCountsBytes(t *testing.T) {
	srv := libreSpeedServer(t, new(atomic.Int64))
	client := srv.Client()
	s, err := runStreams(context.Background(), 3, 200*time.Millisecond, func(ctx context.Context, n *atomic.Int64) error {
		return libreDownload(ctx, client, srv.URL+"/backend/", n)
	})
	if err != nil {
		t.Fatalf("download: %v", err)
	}
	if s.Bytes != 3<<20 {
		t.Fatalf("download counted %d bytes, want %d (1 MiB per stream)", s.Bytes, 3<<20)
	}
}

func TestRunLibreSpeed(t *testing.T) {
	var uploaded atomic.Int64
	srv := libreSpeedServer(t, &uploaded)
	opts := Options{LibreSpeedURL: srv.URL + "/", Duration: 200 * time.Millisecond, Streams: 2, Logger: quiet()}
	res, err := Run(context.Background(), opts)
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if res.Method != MethodLibreSpeed || res.Server != opts.LibreSpeedURL || res.Fallback != "" ||
		res.DownloadMbps <= 0 || res.UploadMbps <= 0 || res.DurationS < 0.4 {
		t.Fatalf("Run = %+v, want librespeed with both speeds over 0.4 s", res)
	}
	if uploaded.Load() == 0 {
		t.Fatal("server received no upload")
	}
}

func TestRunFallsBackToNDT7(t *testing.T) {
	closed := httptest.NewServer(http.NotFoundHandler())
	closed.Close() // nothing listens on the port any more
	broken := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "bad gateway", http.StatusBadGateway)
	}))
	t.Cleanup(broken.Close)

	ndt7URL := ndt7Server(t, func(test string, rw *bufio.ReadWriter) {
		switch test {
		case "download":
			serverFrame(rw, true, opBinary, make([]byte, 64<<10))
			serverFrame(rw, true, opClose, closeNormal)
			_ = rw.Flush()
			_, _, _ = clientFrame(rw.Reader)
		case "upload":
			for {
				if op, _, err := clientFrame(rw.Reader); err != nil || op == opClose {
					return
				}
			}
		}
	})

	for name, libreURL := range map[string]string{"connection refused": closed.URL, "HTTP 502": broken.URL} {
		t.Run(name, func(t *testing.T) {
			opts := Options{LibreSpeedURL: libreURL, NDT7URL: ndt7URL, Duration: 100 * time.Millisecond, Logger: quiet()}
			res, err := Run(context.Background(), opts)
			if err != nil {
				t.Fatalf("Run: %v", err)
			}
			if res.Method != MethodNDT7 || res.Server != ndt7URL || !strings.HasPrefix(res.Fallback, "LibreSpeed: download") ||
				res.DownloadMbps <= 0 || res.UploadMbps <= 0 || res.DurationS <= 0 {
				t.Fatalf("Run = %+v, want ndt7 with both speeds and the LibreSpeed failure", res)
			}
		})
	}
}

func TestRunWithoutServer(t *testing.T) {
	if _, err := Run(context.Background(), Options{Logger: quiet()}); err == nil {
		t.Fatal("Run without addresses: want error")
	}
	closed := httptest.NewServer(http.NotFoundHandler())
	closed.Close()
	if _, err := Run(context.Background(), Options{LibreSpeedURL: closed.URL, Logger: quiet()}); err == nil {
		t.Fatal("Run with LibreSpeed down and no ndt7: want error")
	}
}

func TestNDT7Download(t *testing.T) {
	const measurement = `{"TCPInfo":{"BytesSent":200000,"ElapsedTime":1000}}`
	payload := make([]byte, 100<<10)
	done := make(chan error, 1)
	url := ndt7Server(t, func(_ string, rw *bufio.ReadWriter) {
		// A fragmented message with a ping inside, a whole one, a measurement, close.
		serverFrame(rw, false, opBinary, payload[:40<<10])
		serverFrame(rw, true, opPing, []byte("rtt"))
		serverFrame(rw, true, opContinuation, payload[40<<10:])
		serverFrame(rw, true, opBinary, payload)
		serverFrame(rw, true, opText, []byte(measurement))
		serverFrame(rw, true, opClose, closeNormal)
		_ = rw.Flush()
		done <- expectFrames(rw.Reader, []byte{opPong, opClose}, []string{"rtt", string(closeNormal)})
	})

	s, err := ndt7Download(context.Background(), url+"/ndt/v7/download", 5*time.Second)
	if err != nil {
		t.Fatalf("ndt7Download: %v", err)
	}
	if want := int64(2*len(payload) + len(measurement)); s.Bytes != want || s.Elapsed >= 5*time.Second {
		t.Fatalf("ndt7Download = %+v, want %d bytes before the deadline", s, want)
	}
	if err := <-done; err != nil {
		t.Fatalf("server: %v", err)
	}
}

func TestNDT7UploadUsesServerReport(t *testing.T) {
	done := make(chan error, 1)
	url := ndt7Server(t, func(_ string, rw *bufio.ReadWriter) {
		done <- func() error {
			for first := true; ; first = false {
				op, p, err := clientFrame(rw.Reader)
				switch {
				case err != nil:
					return err
				case op == opClose:
					return nil
				case op == opPong:
				case op != opBinary:
					return fmt.Errorf("opcode %#x, want binary, pong or close", op)
				case first && len(p) != ndt7MinMessage:
					return fmt.Errorf("first message %d bytes, want %d", len(p), ndt7MinMessage)
				case first:
					// A ping after the measurement, as ndt-server does.
					serverFrame(rw, true, opText, []byte(`{"TCPInfo":{"BytesReceived":1000000,"ElapsedTime":500000}}`))
					serverFrame(rw, true, opPing, []byte("1"))
					if err := rw.Flush(); err != nil {
						return err
					}
				}
			}
		}()
	})

	s, err := ndt7Upload(context.Background(), url+"/ndt/v7/upload", 200*time.Millisecond)
	if err != nil {
		t.Fatalf("ndt7Upload: %v", err)
	}
	// 1 000 000 bytes in 0.5 s by the server's count.
	if s.Bytes != 1_000_000 || s.Elapsed != 500*time.Millisecond || s.mbps() != 16 {
		t.Fatalf("ndt7Upload = %+v (%v Mbit/s), want the server report: 16 Mbit/s", s, s.mbps())
	}
	if err := <-done; err != nil {
		t.Fatalf("server: %v", err)
	}
}

// ndt7Server is a fake ndt7 server; after the handshake handle gets the test
// name and the connection. It returns the ws:// address of the server.
func ndt7Server(t *testing.T, handle func(test string, rw *bufio.ReadWriter)) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Upgrade") != "websocket" || r.Header.Get("Sec-WebSocket-Protocol") != ndt7Protocol {
			http.Error(w, "ndt7 handshake expected", http.StatusBadRequest)
			return
		}
		conn, rw, err := http.NewResponseController(w).Hijack()
		if err != nil {
			return
		}
		defer conn.Close()
		fmt.Fprintf(rw, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"+
			"Sec-WebSocket-Accept: %s\r\nSec-WebSocket-Protocol: %s\r\n\r\n", wsAccept(r.Header.Get("Sec-WebSocket-Key")), ndt7Protocol)
		if rw.Flush() != nil {
			return
		}
		handle(strings.TrimPrefix(r.URL.Path, "/ndt/v7/"), rw)
		_ = rw.Flush()
	}))
	t.Cleanup(srv.Close)
	return "ws" + strings.TrimPrefix(srv.URL, "http")
}

// serverFrame writes an unmasked frame, as a server does.
func serverFrame(w io.Writer, fin bool, op byte, payload []byte) {
	if fin {
		op |= 0x80
	}
	hdr := []byte{op, 0}
	switch l := len(payload); {
	case l <= 125:
		hdr[1] = byte(l)
	case l <= 0xffff:
		hdr[1] = 126
		hdr = binary.BigEndian.AppendUint16(hdr, uint16(l))
	default:
		hdr[1] = 127
		hdr = binary.BigEndian.AppendUint64(hdr, uint64(l))
	}
	_, _ = w.Write(hdr)
	_, _ = w.Write(payload)
}

// clientFrame reads one frame of the client, which must be masked, and unmasks it.
func clientFrame(r *bufio.Reader) (op byte, payload []byte, err error) {
	var hdr [2]byte
	if _, err := io.ReadFull(r, hdr[:]); err != nil {
		return 0, nil, err
	}
	if hdr[1]&0x80 == 0 {
		return 0, nil, errors.New("client frame is not masked")
	}
	size := uint64(hdr[1] & 0x7f)
	var ext [8]byte
	switch size {
	case 126:
		if _, err := io.ReadFull(r, ext[:2]); err != nil {
			return 0, nil, err
		}
		size = uint64(binary.BigEndian.Uint16(ext[:2]))
	case 127:
		if _, err := io.ReadFull(r, ext[:]); err != nil {
			return 0, nil, err
		}
		size = binary.BigEndian.Uint64(ext[:])
	}
	var mask [4]byte
	if _, err := io.ReadFull(r, mask[:]); err != nil {
		return 0, nil, err
	}
	payload = make([]byte, size)
	if _, err := io.ReadFull(r, payload); err != nil {
		return 0, nil, err
	}
	for i := range payload {
		payload[i] ^= mask[i%4]
	}
	return hdr[0] & 0x0f, payload, nil
}

// expectFrames reads frames of the client and compares opcodes and payloads.
func expectFrames(r *bufio.Reader, ops []byte, payloads []string) error {
	for i, want := range ops {
		op, p, err := clientFrame(r)
		if err != nil {
			return err
		}
		if op != want || string(p) != payloads[i] {
			return fmt.Errorf("client frame %#x %q, want %#x %q", op, p, want, payloads[i])
		}
	}
	return nil
}
