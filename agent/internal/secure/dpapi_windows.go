//go:build windows

package secure

import (
	"unsafe"

	"golang.org/x/sys/windows"
)

// entropy ties the blob to this agent: another program running under the
// same account cannot unseal it with a plain CryptUnprotectData call.
var entropy = []byte("vko-agent device secret")

func seal(secret []byte) ([]byte, error) {
	var out windows.DataBlob
	err := windows.CryptProtectData(blob(secret), nil, blob(entropy), 0, nil,
		windows.CRYPTPROTECT_UI_FORBIDDEN, &out)
	if err != nil {
		return nil, err
	}
	return takeBlob(&out), nil
}

func unseal(sealed []byte) ([]byte, error) {
	var out windows.DataBlob
	err := windows.CryptUnprotectData(blob(sealed), nil, blob(entropy), 0, nil,
		windows.CRYPTPROTECT_UI_FORBIDDEN, &out)
	if err != nil {
		return nil, err
	}
	return takeBlob(&out), nil
}

func blob(b []byte) *windows.DataBlob {
	if len(b) == 0 {
		return &windows.DataBlob{}
	}
	return &windows.DataBlob{Size: uint32(len(b)), Data: &b[0]}
}

// takeBlob copies the DPAPI output into Go memory and frees the original.
func takeBlob(b *windows.DataBlob) []byte {
	defer windows.LocalFree(windows.Handle(unsafe.Pointer(b.Data))) //nolint:errcheck // nothing to do on failure
	return append([]byte(nil), unsafe.Slice(b.Data, b.Size)...)
}
