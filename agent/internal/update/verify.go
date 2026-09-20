package update

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
)

// ErrHashMismatch is a downloaded file whose hash is not the one the server
// declared: a broken download, a wrong address or a substituted file. Nothing
// is installed after it (plan.md §4.6, ТЗ п. 20).
var ErrHashMismatch = errors.New("sha256 файла не совпал с релизом")

// Verify hashes the file at path with SHA-256 and compares the result with
// the hash of the release. Both are compared as lower-case hex strings; the
// hash is public, so a plain comparison is enough — it guards against a
// corrupted or substituted file, not against a timing attack.
//
// A mismatch deletes the file — a file the agent will not install has no
// reason to stay on a school computer — and returns an error that satisfies
// errors.Is(err, ErrHashMismatch) and carries both hashes.
func Verify(path, want string) error {
	got, err := fileSHA256(path)
	if err != nil {
		return err
	}
	if got == strings.ToLower(strings.TrimSpace(want)) {
		return nil
	}
	mismatch := fmt.Errorf("%w: ожидался %s, получен %s", ErrHashMismatch, want, got)
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("%w; файл %s не удалён: %w", mismatch, path, err)
	}
	return mismatch
}

// fileSHA256 is the hash of the file at path in lower-case hex.
func fileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", fmt.Errorf("чтение %s: %w", path, err)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
