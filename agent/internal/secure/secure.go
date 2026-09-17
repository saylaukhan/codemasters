// Package secure keeps agent secrets (the device token) on disk.
//
// On Windows the secret is encrypted with DPAPI under the service account
// (LocalService), so the file is useless on another computer or to another
// account. Elsewhere it is a file readable only by its owner (mode 600).
// ADR-005, ТЗ п. 12.
package secure

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// WriteSecret seals secret and replaces the file at path atomically.
func WriteSecret(path string, secret []byte) error {
	if len(secret) == 0 {
		return errors.New("secure: пустой секрет")
	}
	sealed, err := seal(secret)
	if err != nil {
		return fmt.Errorf("secure: шифрование: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, sealed, 0o600); err != nil {
		return err
	}
	// WriteFile keeps the mode of an existing file; make sure it is 600.
	if err := os.Chmod(tmp, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// ReadSecret reads and unseals the file at path. A missing file returns an
// error that satisfies errors.Is(err, os.ErrNotExist).
func ReadSecret(path string) ([]byte, error) {
	sealed, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	secret, err := unseal(sealed)
	if err != nil {
		return nil, fmt.Errorf("secure: расшифровка %s: %w", path, err)
	}
	return secret, nil
}
