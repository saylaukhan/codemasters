package speed

import (
	"context"
	"errors"
	"fmt"
	"io"
	"math/rand/v2"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// uploadChunk is the body of one upload request, as in the LibreSpeed web client.
const uploadChunk = 20 << 20

// runLibreSpeed measures with a LibreSpeed server: each direction is several
// HTTP streams repeating requests until the time is up.
func runLibreSpeed(ctx context.Context, opts Options) (Result, error) {
	down, up := downloadStreams, uploadStreams
	if opts.Streams > 0 {
		down, up = opts.Streams, opts.Streams
	}
	tr := http.DefaultTransport.(*http.Transport).Clone()
	// Random payload does not compress: gzip would only cost CPU.
	tr.DisableCompression = true
	tr.MaxIdleConnsPerHost = down
	defer tr.CloseIdleConnections()
	client := &http.Client{Transport: tr}
	base := strings.TrimRight(opts.LibreSpeedURL, "/") + "/backend/"

	dl, err := runStreams(ctx, down, opts.Duration, func(ctx context.Context, n *atomic.Int64) error {
		return libreDownload(ctx, client, base, n)
	})
	if err != nil {
		return Result{}, fmt.Errorf("download: %w", err)
	}
	ul, err := runStreams(ctx, up, opts.Duration, func(ctx context.Context, n *atomic.Int64) error {
		return libreUpload(ctx, client, base, n)
	})
	if err != nil {
		return Result{}, fmt.Errorf("upload: %w", err)
	}
	return Result{
		Method:       MethodLibreSpeed,
		Server:       opts.LibreSpeedURL,
		DownloadMbps: dl.mbps(),
		UploadMbps:   ul.mbps(),
	}, nil
}

// runStreams repeats request in n parallel streams for d and sums the bytes
// they moved into one sample. A failed stream is not restarted; the direction
// fails when every stream failed before the time was up or nothing moved.
func runStreams(ctx context.Context, n int, d time.Duration, request func(context.Context, *atomic.Int64) error) (sample, error) {
	parent := ctx
	ctx, cancel := context.WithTimeout(ctx, d)
	defer cancel()

	var total atomic.Int64
	errs := make([]error, n)
	var wg sync.WaitGroup
	start := time.Now()
	for i := range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for ctx.Err() == nil {
				if err := request(ctx, &total); err != nil {
					if ctx.Err() == nil {
						errs[i] = err
					}
					return
				}
			}
		}()
	}
	wg.Wait()
	s := sample{Bytes: total.Load(), Elapsed: time.Since(start)}

	if err := parent.Err(); err != nil {
		return sample{}, err
	}
	failed := 0
	for _, err := range errs {
		if err != nil {
			failed++
		}
	}
	switch {
	case failed == n:
		return sample{}, errs[0]
	case s.Bytes == 0:
		return sample{}, errors.New("сервер не передал данных")
	}
	return s, nil
}

// libreDownload reads one garbage.php response (100 MiB of random bytes).
func libreDownload(ctx context.Context, client *http.Client, base string, n *atomic.Int64) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, base+"garbage.php?ckSize=100&r="+nonce(), nil)
	if err != nil {
		return err
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("garbage.php: HTTP %d", resp.StatusCode)
	}
	got, err := io.Copy(counter{n}, resp.Body)
	if err == nil && got == 0 {
		return errors.New("garbage.php: пустой ответ")
	}
	return err
}

// libreUpload sends one uploadChunk to empty.php, which discards it. Bytes are
// counted as the transport takes them, like the upload progress of a browser.
func libreUpload(ctx context.Context, client *http.Client, base string, n *atomic.Int64) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, base+"empty.php?r="+nonce(),
		&fillerReader{left: uploadChunk, sent: n})
	if err != nil {
		return err
	}
	req.ContentLength = uploadChunk
	req.Header.Set("Content-Type", "application/octet-stream")
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("empty.php: HTTP %d", resp.StatusCode)
	}
	return nil
}

// nonce keeps proxies from answering from cache.
func nonce() string {
	return strconv.FormatUint(rand.Uint64(), 36)
}

// counter is a writer that only counts.
type counter struct{ n *atomic.Int64 }

func (c counter) Write(p []byte) (int, error) {
	c.n.Add(int64(len(p)))
	return len(p), nil
}

// fillerReader yields left bytes of filler and counts them into sent.
type fillerReader struct {
	left int64
	off  int
	sent *atomic.Int64
}

func (r *fillerReader) Read(p []byte) (int, error) {
	if r.left <= 0 {
		return 0, io.EOF
	}
	if int64(len(p)) > r.left {
		p = p[:r.left]
	}
	buf := filler()
	n := copy(p, buf[r.off:])
	r.off = (r.off + n) % len(buf)
	r.left -= int64(n)
	r.sent.Add(int64(n))
	return n, nil
}
