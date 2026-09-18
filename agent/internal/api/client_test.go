package api

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRegister(t *testing.T) {
	var got RegisterRequest
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/devices/register" {
			t.Errorf("request = %s %s, want POST /api/devices/register", r.Method, r.URL.Path)
		}
		if auth := r.Header.Get("Authorization"); auth != "" {
			t.Errorf("Authorization = %q, want none on registration", auth)
		}
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode body: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"device_id": 42, "device_token": "tok-42"}`))
	}))
	defer srv.Close()

	req := RegisterRequest{EnrollmentCode: "VKO-7F3K-92QD", DeviceUID: "uid-1", AgentVersion: "dev", Room: "Серверная"}
	resp, err := New(srv.URL+"/", "").Register(context.Background(), req)
	if err != nil {
		t.Fatalf("Register: %v", err)
	}
	if resp.DeviceID != 42 || resp.DeviceToken != "tok-42" {
		t.Fatalf("Register = %+v, want device 42 with tok-42", resp)
	}
	if got != req {
		t.Fatalf("server got %+v, want %+v", got, req)
	}
}

func TestRegisterProblem(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"type": "enrollment_code_expired", "title": "Код просрочен",
			"status": 400, "detail": "Срок действия кода истёк"}`))
	}))
	defer srv.Close()

	_, err := New(srv.URL, "").Register(context.Background(), RegisterRequest{EnrollmentCode: "X"})
	var pe *ProblemError
	if !errors.As(err, &pe) {
		t.Fatalf("Register error = %v, want *ProblemError", err)
	}
	if pe.Status != 400 || pe.Type != "enrollment_code_expired" || pe.Temporary() {
		t.Fatalf("problem = %+v (temporary %v), want final 400 enrollment_code_expired", pe, pe.Temporary())
	}
}

func TestProblemTemporaryWithoutJSONBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "<html>bad gateway</html>", http.StatusBadGateway)
	}))
	defer srv.Close()

	_, err := New(srv.URL, "").Register(context.Background(), RegisterRequest{})
	var pe *ProblemError
	if !errors.As(err, &pe) || pe.Status != http.StatusBadGateway || !pe.Temporary() {
		t.Fatalf("Register error = %v, want temporary 502 problem", err)
	}
}

func TestDeviceAuthorizationHeader(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if auth := r.Header.Get("Authorization"); auth != "Device tok-42" {
			t.Errorf("Authorization = %q, want %q", auth, "Device tok-42")
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()

	if err := New(srv.URL, "tok-42").do(context.Background(), http.MethodPost, "/devices/heartbeat", map[string]string{}, nil); err != nil {
		t.Fatalf("do: %v", err)
	}
}

func TestWhoAmI(t *testing.T) {
	answer := `{"external_ip": "95.56.12.34"}`
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/agent/whoami" || r.Header.Get("Authorization") != "Device tok-42" {
			t.Errorf("request = %s %s (%q), want GET /api/agent/whoami with the device token",
				r.Method, r.URL.Path, r.Header.Get("Authorization"))
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(answer))
	}))
	defer srv.Close()

	ip, err := New(srv.URL, "tok-42").WhoAmI(context.Background())
	if err != nil || ip != "95.56.12.34" {
		t.Fatalf("WhoAmI = %q, %v, want 95.56.12.34", ip, err)
	}
	answer = `{"external_ip": "unknown"}`
	if _, err := New(srv.URL, "tok-42").WhoAmI(context.Background()); err == nil {
		t.Fatal("WhoAmI with an invalid external_ip: want error")
	}
}

// TestRotateToken: the new token is asked for with the current one, and the
// requests after SetToken carry only the new token (T-36).
func TestRotateToken(t *testing.T) {
	var auths []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		auths = append(auths, r.Header.Get("Authorization"))
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/api/agent/token":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"device_id": 7, "device_token": "7.new"}`))
		case r.Header.Get("Authorization") == "Device 7.new":
			w.WriteHeader(http.StatusNoContent)
		default:
			w.Header().Set("Content-Type", "application/problem+json")
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"type": "unauthorized", "status": 401}`))
		}
	}))
	defer srv.Close()

	c := New(srv.URL, "7.old")
	resp, err := c.RotateToken(context.Background())
	if err != nil {
		t.Fatalf("RotateToken: %v", err)
	}
	if resp.DeviceID != 7 || resp.DeviceToken != "7.new" {
		t.Fatalf("RotateToken = %+v, want device 7 with 7.new", resp)
	}
	c.SetToken(resp.DeviceToken)
	if err := c.do(context.Background(), http.MethodPost, "/devices/heartbeat", nil, nil); err != nil {
		t.Fatalf("request with the new token: %v", err)
	}
	if c.Token() != "7.new" || len(auths) != 2 || auths[0] != "Device 7.old" || auths[1] != "Device 7.new" {
		t.Fatalf("token %q, Authorization headers %q; want the old one for the rotation, then the new one", c.Token(), auths)
	}
}
