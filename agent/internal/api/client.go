// Package api is the agent's HTTP client to the monitoring server (plan.md §10).
//
// Every request except registration carries `Authorization: Device <token>`
// (ADR-005). Server errors arrive as application/problem+json (ADR-009) and
// are returned as *ProblemError.
package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
)

// requestTimeout bounds one API call; speed tests do not go through this client.
const requestTimeout = 30 * time.Second

// maxErrorBody limits how much of an error response is read.
const maxErrorBody = 64 << 10

// Client calls the monitoring API. The token is empty until the device is
// registered and may be replaced while requests are running (T-36).
type Client struct {
	BaseURL string
	HTTP    *http.Client

	mu    sync.RWMutex
	token string
}

// New returns a client for the server at baseURL (config server_url).
func New(baseURL, token string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		HTTP:    &http.Client{Timeout: requestTimeout},
		token:   token,
	}
}

// Token returns the device token the requests carry.
func (c *Client) Token() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.token
}

// SetToken makes the following requests carry token: the heartbeat, the
// queue and the configuration share one client.
func (c *Client) SetToken(token string) {
	c.mu.Lock()
	c.token = token
	c.mu.Unlock()
}

// ProblemError is an error response of the server (RFC 9457, ADR-009).
type ProblemError struct {
	Status int    `json:"status"`
	Type   string `json:"type"`
	Title  string `json:"title"`
	Detail string `json:"detail"`
	// RetryAfter is the Retry-After header of the answer (429 or 503), 0 when absent.
	RetryAfter time.Duration `json:"-"`
}

func (e *ProblemError) Error() string {
	msg := fmt.Sprintf("сервер ответил %d", e.Status)
	if e.Type != "" {
		msg += " " + e.Type
	}
	if e.Detail != "" {
		msg += ": " + e.Detail
	} else if e.Title != "" {
		msg += ": " + e.Title
	}
	return msg
}

// Temporary reports whether repeating the same request later may succeed:
// server-side failures, rate limiting and timeouts. Other 4xx answers are final.
func (e *ProblemError) Temporary() bool {
	return e.Status >= 500 || e.Status == http.StatusTooManyRequests ||
		e.Status == http.StatusRequestTimeout
}

// newRequest builds a request to path (relative to /api) with the headers
// every call of the agent carries.
func (c *Client) newRequest(ctx context.Context, method, path string, body io.Reader) (*http.Request, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+"/api"+path, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "vko-agent/"+buildinfo.Version)
	if token := c.Token(); token != "" {
		req.Header.Set("Authorization", "Device "+token)
	}
	return req, nil
}

// problemFrom reads a failed answer as problem+json (ADR-009).
func problemFrom(resp *http.Response) *ProblemError {
	pe := &ProblemError{}
	// Not every failure is problem+json (a proxy may answer HTML): keep the status anyway.
	_ = json.NewDecoder(io.LimitReader(resp.Body, maxErrorBody)).Decode(pe)
	pe.Status = resp.StatusCode
	pe.RetryAfter = parseRetryAfter(resp.Header.Get("Retry-After"), time.Now())
	return pe
}

// do sends a JSON request to path (relative to /api) and decodes a 2xx JSON
// answer into out when out is not nil.
func (c *Client) do(ctx context.Context, method, path string, in, out any) error {
	var body io.Reader
	if in != nil {
		data, err := json.Marshal(in)
		if err != nil {
			return err
		}
		body = bytes.NewReader(data)
	}
	req, err := c.newRequest(ctx, method, path, body)
	if err != nil {
		return err
	}
	if in != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return problemFrom(resp)
	}
	if out == nil {
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("разбор ответа %s %s: %w", method, path, err)
	}
	return nil
}
