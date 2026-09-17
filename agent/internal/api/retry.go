package api

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// RetryFirst and RetryMax bound the pause between resend attempts after a
// network error or a server failure (ADR-006).
const (
	RetryFirst = 30 * time.Second
	RetryMax   = time.Hour
)

// retryAfterMax caps Retry-After, so a broken proxy cannot stop sending for days.
const retryAfterMax = 24 * time.Hour

// Backoff counts failed attempts in a row and returns the pause before the
// next one: RetryFirst doubled after every failure up to RetryMax, but not
// shorter than the Retry-After of the server (429, T-51). The zero value is
// ready to use.
type Backoff struct {
	delay time.Duration
}

// Next returns the pause after the failure err.
func (b *Backoff) Next(err error) time.Duration {
	if b.delay == 0 {
		b.delay = RetryFirst
	} else {
		b.delay = min(b.delay*2, RetryMax)
	}
	return max(b.delay, RetryAfter(err))
}

// Reset starts over after a successful attempt.
func (b *Backoff) Reset() {
	b.delay = 0
}

// RetryAfter returns the pause the server asked for in Retry-After, 0 when it did not.
func RetryAfter(err error) time.Duration {
	var pe *ProblemError
	if !errors.As(err, &pe) {
		return 0
	}
	return pe.RetryAfter
}

// parseRetryAfter reads Retry-After as seconds or an HTTP date (RFC 9110 §10.2.3).
func parseRetryAfter(value string, now time.Time) time.Duration {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0
	}
	var d time.Duration
	if secs, err := strconv.ParseInt(value, 10, 64); err == nil {
		d = time.Duration(min(secs, int64(retryAfterMax/time.Second))) * time.Second
	} else if at, err := http.ParseTime(value); err == nil {
		d = at.Sub(now)
	}
	return min(max(d, 0), retryAfterMax)
}
