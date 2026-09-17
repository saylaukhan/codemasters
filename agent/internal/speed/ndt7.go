package speed

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"
)

// ndt7 protocol constants (m-lab/ndt-server, spec/ndt7-protocol.md).
const (
	ndt7Protocol = "net.measurementlab.ndt.v7"
	// Upload messages start small and double while the line keeps up. They stop
	// at 64 KiB, not at the 1 MiB of the spec: the server stops reporting
	// without pongs, and a pong waits behind the message being written.
	ndt7MinMessage  = 1 << 13
	ndt7MaxMessage  = 1 << 16
	ndt7ScaleFactor = 16
	// The server runs a test for 10 s from its own start and then closes it;
	// ndt7Grace is how much longer the agent waits for that close (the server
	// gives up at 15 s). It also lets the last upload message finish: a frame
	// cut in the middle breaks the stream.
	ndt7Grace = 5 * time.Second
)

// ndt7Measurement is the part of a server measurement message the agent reads.
// ndt-server fills TCPInfo (on Linux), not AppInfo; its own upload rate is
// BytesReceived over ElapsedTime.
type ndt7Measurement struct {
	TCPInfo *struct {
		BytesReceived int64
		// ElapsedTime is in microseconds since the test started.
		ElapsedTime int64
	}
}

// runNDT7 measures with an ndt7 server: one WebSocket per direction.
func runNDT7(ctx context.Context, opts Options) (Result, error) {
	base := strings.TrimRight(opts.NDT7URL, "/") + "/ndt/v7/"
	dl, err := ndt7Download(ctx, base+"download", opts.Duration)
	if err != nil {
		return Result{}, fmt.Errorf("download: %w", err)
	}
	ul, err := ndt7Upload(ctx, base+"upload", opts.Duration)
	if err != nil {
		return Result{}, fmt.Errorf("upload: %w", err)
	}
	return Result{
		Method:       MethodNDT7,
		Server:       opts.NDT7URL,
		DownloadMbps: dl.mbps(),
		UploadMbps:   ul.mbps(),
	}, nil
}

// ndt7Download counts what the server sends until it closes the test, at
// most d plus ndt7Grace.
func ndt7Download(ctx context.Context, rawURL string, d time.Duration) (sample, error) {
	parent := ctx
	ctx, cancel := context.WithTimeout(ctx, d+ndt7Grace)
	defer cancel()
	c, err := dialWS(ctx, rawURL, ndt7Protocol)
	if err != nil {
		return sample{}, err
	}
	defer c.Close()
	stop := context.AfterFunc(ctx, func() { _ = c.conn.SetDeadline(time.Now()) })
	defer stop()

	start := time.Now()
	var s sample
	var n int64
	for {
		_, n, _, err = c.readMessage()
		s.Bytes += n
		if err != nil {
			break
		}
	}
	s.Elapsed = time.Since(start)

	if err := parent.Err(); err != nil {
		return sample{}, err
	}
	if s.Bytes == 0 {
		if err == nil {
			err = errors.New("пустые сообщения")
		}
		return sample{}, fmt.Errorf("сервер не передал данных: %w", err)
	}
	return s, nil
}

// ndt7Upload sends filler for d or until the server closes the test. The
// speed is what the server reports it has received: bytes written by the
// agent include what still sits in the socket buffers. Without a server report
// covering at least half of the test the written bytes are used.
func ndt7Upload(ctx context.Context, rawURL string, d time.Duration) (sample, error) {
	parent := ctx
	ctx, cancel := context.WithTimeout(ctx, d+ndt7Grace)
	defer cancel()
	c, err := dialWS(ctx, rawURL, ndt7Protocol)
	if err != nil {
		return sample{}, err
	}
	stop := context.AfterFunc(ctx, func() { _ = c.conn.SetDeadline(time.Now()) })
	defer stop()

	var reported sample
	readDone := make(chan struct{})
	go func() {
		defer close(readDone)
		for {
			op, _, text, err := c.readMessage()
			if err != nil {
				// The test is over: do not wait for the data frame in flight.
				_ = c.conn.SetWriteDeadline(time.Now())
				return
			}
			var m ndt7Measurement
			if op == opText && json.Unmarshal(text, &m) == nil && m.TCPInfo != nil && m.TCPInfo.ElapsedTime > 0 {
				reported = sample{Bytes: m.TCPInfo.BytesReceived, Elapsed: time.Duration(m.TCPInfo.ElapsedTime) * time.Microsecond}
			}
		}
	}()

	start := time.Now()
	var sent sample
	size := ndt7MinMessage
	for time.Since(start) < d && !closed(readDone) {
		if err := c.writeFrame(opBinary, filler()[:size], true); err != nil {
			break
		}
		sent.Bytes += int64(size)
		if size < ndt7MaxMessage && sent.Bytes >= int64(size)*ndt7ScaleFactor {
			size *= 2
		}
	}
	sent.Elapsed = time.Since(start)
	_ = c.Close()
	<-readDone

	if err := parent.Err(); err != nil {
		return sample{}, err
	}
	switch {
	case reported.Bytes > 0 && reported.Elapsed >= sent.Elapsed/2:
		return reported, nil
	case sent.Bytes > 0:
		return sent, nil
	}
	return sample{}, errors.New("не удалось отправить данные")
}

func closed(ch <-chan struct{}) bool {
	select {
	case <-ch:
		return true
	default:
		return false
	}
}
