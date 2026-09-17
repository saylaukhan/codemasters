package speed

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha1"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"sync"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
)

// A minimal RFC 6455 client, just enough for ndt7: one WebSocket test does not
// justify a dependency (AGENTS.md §2.6).

const (
	opContinuation byte = 0x0
	opText         byte = 0x1
	opBinary       byte = 0x2
	opClose        byte = 0x8
	opPing         byte = 0x9
	opPong         byte = 0xA
)

// maxTextMessage bounds the text kept by readMessage; ndt7 measurements are a few KiB.
const maxTextMessage = 64 << 10

// closeNormal is the payload of a close frame with status 1000.
var closeNormal = []byte{0x03, 0xe8}

type wsConn struct {
	conn net.Conn
	br   *bufio.Reader
	wmu  sync.Mutex
}

// dialWS opens a ws:// or wss:// connection with the subprotocol; ctx bounds
// the dial and the handshake.
func dialWS(ctx context.Context, rawURL, protocol string) (*wsConn, error) {
	u, err := url.Parse(rawURL)
	if err != nil || (u.Scheme != "ws" && u.Scheme != "wss") || u.Hostname() == "" {
		return nil, fmt.Errorf("адрес %q должен быть ws(s)://хост", rawURL)
	}
	addr := u.Host
	if u.Port() == "" {
		addr = net.JoinHostPort(u.Hostname(), map[string]string{"ws": "80", "wss": "443"}[u.Scheme])
	}
	var conn net.Conn
	if u.Scheme == "wss" {
		conn, err = (&tls.Dialer{}).DialContext(ctx, "tcp", addr)
	} else {
		conn, err = (&net.Dialer{}).DialContext(ctx, "tcp", addr)
	}
	if err != nil {
		return nil, err
	}
	stop := context.AfterFunc(ctx, func() { _ = conn.SetDeadline(time.Now()) })
	defer stop()

	c, err := handshake(conn, u, protocol)
	if err != nil {
		_ = conn.Close()
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, err
	}
	return c, nil
}

func handshake(conn net.Conn, u *url.URL, protocol string) (*wsConn, error) {
	var raw [16]byte
	_, _ = rand.Read(raw[:])
	key := base64.StdEncoding.EncodeToString(raw[:])
	_, err := fmt.Fprintf(conn, "GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"+
		"Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: %s\r\nUser-Agent: vko-agent/%s\r\n\r\n",
		u.RequestURI(), u.Host, key, protocol, buildinfo.Version)
	if err != nil {
		return nil, err
	}
	br := bufio.NewReaderSize(conn, 64<<10)
	resp, err := http.ReadResponse(br, nil)
	if err != nil {
		return nil, err
	}
	_ = resp.Body.Close()
	switch {
	case resp.StatusCode != http.StatusSwitchingProtocols:
		return nil, fmt.Errorf("сервер ответил %s вместо 101", resp.Status)
	case resp.Header.Get("Sec-WebSocket-Accept") != wsAccept(key):
		return nil, errors.New("неверный Sec-WebSocket-Accept")
	case resp.Header.Get("Sec-WebSocket-Protocol") != protocol:
		return nil, fmt.Errorf("сервер не принял подпротокол %s", protocol)
	}
	return &wsConn{conn: conn, br: br}, nil
}

// wsAccept is the Sec-WebSocket-Accept the server must return for key.
func wsAccept(key string) string {
	sum := sha1.Sum([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	return base64.StdEncoding.EncodeToString(sum[:])
}

// readMessage reads the next data message and returns its opcode and size.
// Payload is counted and dropped, except a text message up to
// maxTextMessage, which is returned. Ping is answered with pong. A close
// frame ends the stream with io.EOF; the answer is sent by Close, so a reader
// running beside a writer never blocks on it. On error n is the size of the
// frames read so far.
func (c *wsConn) readMessage() (op byte, n int64, text []byte, err error) {
	var hdr [8]byte
	keepText := false
	for {
		if _, err := io.ReadFull(c.br, hdr[:2]); err != nil {
			return op, n, nil, err
		}
		fin, frameOp := hdr[0]&0x80 != 0, hdr[0]&0x0f
		if hdr[1]&0x80 != 0 {
			return op, n, nil, errors.New("websocket: сервер прислал маскированный кадр")
		}
		size := uint64(hdr[1] & 0x7f)
		switch size {
		case 126:
			if _, err := io.ReadFull(c.br, hdr[:2]); err != nil {
				return op, n, nil, err
			}
			size = uint64(binary.BigEndian.Uint16(hdr[:2]))
		case 127:
			if _, err := io.ReadFull(c.br, hdr[:8]); err != nil {
				return op, n, nil, err
			}
			size = binary.BigEndian.Uint64(hdr[:8])
		}

		if frameOp >= opClose {
			if size > 125 {
				return op, n, nil, errors.New("websocket: управляющий кадр больше 125 байт")
			}
			payload := make([]byte, size)
			if _, err := io.ReadFull(c.br, payload); err != nil {
				return op, n, nil, err
			}
			switch frameOp {
			case opClose:
				return op, n, nil, io.EOF
			case opPing:
				if err := c.writeFrame(opPong, payload, false); err != nil {
					return op, n, nil, err
				}
			}
			continue
		}

		if frameOp != opContinuation {
			op, text = frameOp, nil
			keepText = frameOp == opText
		}
		if keepText && uint64(len(text))+size <= maxTextMessage {
			start := len(text)
			text = append(text, make([]byte, size)...)
			if _, err := io.ReadFull(c.br, text[start:]); err != nil {
				return op, n, nil, err
			}
		} else {
			keepText, text = false, nil
			if _, err := io.CopyN(io.Discard, c.br, int64(size)); err != nil {
				return op, n, nil, err
			}
		}
		n += int64(size)
		if fin {
			return op, n, text, nil
		}
	}
}

// writeFrame sends one final frame. Client frames must carry a mask; the
// payload is XORed with it unless it is random filler, whose content nobody
// reads, so masking it would only burn CPU.
func (c *wsConn) writeFrame(op byte, payload []byte, filler bool) error {
	var hdr [14]byte
	hdr[0] = 0x80 | op
	h := 2
	switch l := len(payload); {
	case l <= 125:
		hdr[1] = byte(l)
	case l <= 0xffff:
		hdr[1] = 126
		binary.BigEndian.PutUint16(hdr[2:], uint16(l))
		h = 4
	default:
		hdr[1] = 127
		binary.BigEndian.PutUint64(hdr[2:], uint64(l))
		h = 10
	}
	hdr[1] |= 0x80
	mask := hdr[h : h+4]
	_, _ = rand.Read(mask)
	h += 4
	if !filler {
		masked := make([]byte, len(payload))
		for i, b := range payload {
			masked[i] = b ^ mask[i%4]
		}
		payload = masked
	}

	c.wmu.Lock()
	defer c.wmu.Unlock()
	bufs := net.Buffers{hdr[:h], payload}
	_, err := bufs.WriteTo(c.conn)
	return err
}

// Close sends a close frame within a second and closes the connection.
func (c *wsConn) Close() error {
	_ = c.conn.SetWriteDeadline(time.Now().Add(time.Second))
	_ = c.writeFrame(opClose, closeNormal, false)
	return c.conn.Close()
}
