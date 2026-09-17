package api

import (
	"context"
	"net/http"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/buildinfo"
)

// Heartbeat is the body of POST /api/devices/heartbeat
// (backend/app/schemas/agent.py HeartbeatRequest): the agent tells the server
// it is alive, by default every 5 minutes (plan.md §4.2).
type Heartbeat struct {
	// SentAt is marshalled as RFC 3339 with the offset of the computer (ADR-014).
	SentAt       time.Time `json:"sent_at"`
	AgentVersion string    `json:"agent_version"`
}

// SendHeartbeat sends one heartbeat; the server answers 204. A network error
// or a timeout means there is no connection, an answer of the server means
// there is one (ТЗ п. 2, ADR-006).
func (c *Client) SendHeartbeat(ctx context.Context, sentAt time.Time) error {
	body := Heartbeat{SentAt: sentAt, AgentVersion: buildinfo.Version}
	return c.do(ctx, http.MethodPost, "/devices/heartbeat", body, nil)
}
