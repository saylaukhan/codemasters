package api

import (
	"context"
	"fmt"
	"net"
	"net/http"
)

// WhoAmI returns the external IP of the device as the server sees it
// (plan.md §4.3, step 2); the server matches it to the line (ADR-012).
func (c *Client) WhoAmI(ctx context.Context) (string, error) {
	var resp struct {
		ExternalIP string `json:"external_ip"`
	}
	if err := c.do(ctx, http.MethodGet, "/agent/whoami", nil, &resp); err != nil {
		return "", err
	}
	if net.ParseIP(resp.ExternalIP) == nil {
		return "", fmt.Errorf("whoami: сервер вернул неверный external_ip %q", resp.ExternalIP)
	}
	return resp.ExternalIP, nil
}
