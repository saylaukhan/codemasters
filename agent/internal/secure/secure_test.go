package secure

import (
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestWriteReadSecret(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sub", "device_token")
	secret := []byte("dt_7f3k92qd-secret-token")

	if err := WriteSecret(path, secret); err != nil {
		t.Fatalf("WriteSecret: %v", err)
	}
	got, err := ReadSecret(path)
	if err != nil {
		t.Fatalf("ReadSecret: %v", err)
	}
	if !bytes.Equal(got, secret) {
		t.Fatalf("ReadSecret = %q, want %q", got, secret)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS == "windows" {
		if bytes.Contains(raw, secret) {
			t.Fatal("file contains the secret in plain text, want DPAPI blob")
		}
	} else {
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if mode := info.Mode().Perm(); mode != 0o600 {
			t.Fatalf("file mode = %o, want 600", mode)
		}
	}
}

func TestWriteSecretOverwrites(t *testing.T) {
	path := filepath.Join(t.TempDir(), "device_token")
	if err := os.WriteFile(path, []byte("old"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := WriteSecret(path, []byte("new-token")); err != nil {
		t.Fatalf("WriteSecret: %v", err)
	}
	got, err := ReadSecret(path)
	if err != nil {
		t.Fatalf("ReadSecret: %v", err)
	}
	if string(got) != "new-token" {
		t.Fatalf("ReadSecret = %q, want %q", got, "new-token")
	}
	if runtime.GOOS != "windows" {
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if mode := info.Mode().Perm(); mode != 0o600 {
			t.Fatalf("file mode after overwrite = %o, want 600", mode)
		}
	}
}

func TestReadSecretMissing(t *testing.T) {
	_, err := ReadSecret(filepath.Join(t.TempDir(), "absent"))
	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("ReadSecret error = %v, want os.ErrNotExist", err)
	}
}

func TestWriteSecretEmpty(t *testing.T) {
	if err := WriteSecret(filepath.Join(t.TempDir(), "t"), nil); err == nil {
		t.Fatal("WriteSecret(nil) = nil, want error")
	}
}
