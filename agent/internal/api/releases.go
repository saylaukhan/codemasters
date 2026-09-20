package api

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"time"
)

// ErrNoRelease is the 404 of GET /api/agent/releases/latest: the update
// channel of this device has no release yet. It is not a failure of the
// server — the agent simply keeps the version it runs (T-50).
var ErrNoRelease = errors.New("на канале обновлений нет релиза")

// sha256Hex is the hash of a release as the server declares it: 64 lower-case
// hex digits (backend/app/schemas/agent.py AgentReleaseResponse).
var sha256Hex = regexp.MustCompile(`^[0-9a-f]{64}$`)

// Release is the answer of GET /api/agent/releases/latest
// (backend/app/schemas/agent.py AgentReleaseResponse): the version the
// channel of this device must run and the file to install (plan.md §4.6).
type Release struct {
	Version string `json:"version"`
	// Channel is pilot or stable; the channel of the device is set in the
	// admin panel, the agent never asks for one (ADR-005).
	Channel string `json:"channel"`
	// DownloadURL is the MSI: an absolute address or one relative to the server.
	DownloadURL string `json:"download_url"`
	// SHA256 is the hash of that file in lower-case hex. The agent installs
	// nothing whose hash does not match it (plan.md §4.6).
	SHA256 string `json:"sha256"`
	// ReleasedAt is RFC 3339 with an offset (ADR-014).
	ReleasedAt time.Time `json:"released_at"`
}

// Validate checks what the agent depends on before it downloads anything.
func (r Release) Validate() error {
	if r.Version == "" {
		return errors.New("релиз: пустая версия")
	}
	if r.DownloadURL == "" {
		return fmt.Errorf("релиз %s: пустой download_url", r.Version)
	}
	if !sha256Hex.MatchString(r.SHA256) {
		return fmt.Errorf("релиз %s: sha256 %q — ожидаются 64 шестнадцатеричные цифры в нижнем регистре",
			r.Version, r.SHA256)
	}
	return nil
}

// GetLatestRelease asks for the release of the update channel of this device.
// The channel comes from the device binding, never from the request (ADR-005).
// A channel without a release answers 404: the error is ErrNoRelease, so the
// caller tells it apart from a server that is down.
func (c *Client) GetLatestRelease(ctx context.Context) (Release, error) {
	var rel Release
	err := c.do(ctx, http.MethodGet, "/agent/releases/latest", nil, &rel)
	var pe *ProblemError
	if errors.As(err, &pe) && pe.Status == http.StatusNotFound {
		return Release{}, ErrNoRelease
	}
	if err != nil {
		return Release{}, err
	}
	return rel, nil
}
