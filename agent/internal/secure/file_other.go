//go:build !windows

package secure

// Outside Windows there is no DPAPI: the secret is stored as is and protected
// by the file mode 600 set in WriteSecret (ADR-005).

func seal(secret []byte) ([]byte, error) { return append([]byte(nil), secret...), nil }

func unseal(sealed []byte) ([]byte, error) { return sealed, nil }
