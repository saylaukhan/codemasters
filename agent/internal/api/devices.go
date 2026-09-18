package api

import (
	"context"
	"errors"
	"net/http"
)

// RegisterRequest is the body of POST /api/devices/register
// (backend/app/schemas/agent.py DeviceRegisterRequest). There is no school
// field: the server takes the school from the enrollment code (ADR-005).
type RegisterRequest struct {
	EnrollmentCode string `json:"enrollment_code"`
	DeviceUID      string `json:"device_uid"`
	Hostname       string `json:"hostname,omitempty"`
	OS             string `json:"os,omitempty"`
	AgentVersion   string `json:"agent_version"`
	Room           string `json:"room,omitempty"`
}

// RegisterResponse carries the device credentials; the token is shown once.
type RegisterResponse struct {
	DeviceID    int64  `json:"device_id"`
	DeviceToken string `json:"device_token"`
}

// Register exchanges a one-time enrollment code for device credentials.
func (c *Client) Register(ctx context.Context, req RegisterRequest) (RegisterResponse, error) {
	var resp RegisterResponse
	if err := c.do(ctx, http.MethodPost, "/devices/register", req, &resp); err != nil {
		return RegisterResponse{}, err
	}
	if resp.DeviceID == 0 || resp.DeviceToken == "" {
		return RegisterResponse{}, errors.New("регистрация: сервер не вернул device_id или device_token")
	}
	return resp, nil
}

// RotateToken exchanges the current device token for a new one when the
// configuration asks for it (token_rotation_required, T-36). The old token
// stops working as soon as the server answers, so the caller saves the new
// one before anything else; the client itself is not changed.
func (c *Client) RotateToken(ctx context.Context) (RegisterResponse, error) {
	var resp RegisterResponse
	if err := c.do(ctx, http.MethodPost, "/agent/token", nil, &resp); err != nil {
		return RegisterResponse{}, err
	}
	if resp.DeviceID == 0 || resp.DeviceToken == "" {
		return RegisterResponse{}, errors.New("замена токена: сервер не вернул device_id или device_token")
	}
	return resp, nil
}
