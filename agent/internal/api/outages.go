package api

import (
	"context"
	"errors"
	"net/http"
	"time"
)

// Outage is the body of POST /api/outages (backend/app/schemas/agent.py
// OutageCreate): a period the agent spent without connection. The device and
// the school come from the token, never from the body (ADR-005).
type Outage struct {
	// StartedAt and EndedAt are marshalled as RFC 3339 with the offset of the computer (ADR-014).
	StartedAt time.Time `json:"started_at"`
	EndedAt   time.Time `json:"ended_at"`
}

// SendOutage sends one finished outage. The idempotency key is the device
// plus started_at, so a duplicate (409 duplicate_outage) is not an error: the
// server already has the outage and the record can be deleted (ADR-006).
func (c *Client) SendOutage(ctx context.Context, startedAt, endedAt time.Time) error {
	body := Outage{StartedAt: startedAt, EndedAt: endedAt}
	err := c.do(ctx, http.MethodPost, "/outages", body, nil)
	var pe *ProblemError
	if errors.As(err, &pe) && pe.Status == http.StatusConflict {
		return nil
	}
	return err
}
