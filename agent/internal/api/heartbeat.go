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

// HeartbeatResponse is the answer of POST /api/devices/heartbeat
// (backend/app/schemas/agent.py HeartbeatResponse): what the server asks of
// the agent besides its schedule.
type HeartbeatResponse struct {
	// MeasureRequestedAt is when an administrator asked for a measurement in
	// the panel (T-79); nil when nothing is asked for. The server repeats the
	// same moment in every answer until the measurement reaches it, so the
	// agent tells a new request from a repeated one by this moment alone.
	MeasureRequestedAt *time.Time `json:"measure_requested_at,omitempty"`
}

// SendHeartbeat sends one heartbeat and returns what the server asks of the
// agent. A network error or a timeout means there is no connection, an answer
// of the server means there is one (ТЗ п. 2, ADR-006).
func (c *Client) SendHeartbeat(ctx context.Context, sentAt time.Time) (HeartbeatResponse, error) {
	body := Heartbeat{SentAt: sentAt, AgentVersion: buildinfo.Version}
	var resp HeartbeatResponse
	if err := c.do(ctx, http.MethodPost, "/devices/heartbeat", body, &resp); err != nil {
		return HeartbeatResponse{}, err
	}
	return resp, nil
}
