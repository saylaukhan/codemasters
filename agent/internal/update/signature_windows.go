//go:build windows

package update

import (
	"errors"
	"fmt"
	"unsafe"

	"golang.org/x/sys/windows"
)

// verifySignature checks the Authenticode signature of the file with
// WinVerifyTrustEx — the same check Windows does when the MSI is opened by
// hand (plan.md §4.6). A file with a broken or untrusted signature is never
// installed; a file with no signature at all returns ErrNotSigned, which the
// caller decides about, because releases are not signed yet (T-49: the
// signtool step of agent-msi.yml is commented out until the department
// certificate is there).
func verifySignature(path string) error {
	name, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return err
	}
	file := &windows.WinTrustFileInfo{
		Size:     uint32(unsafe.Sizeof(windows.WinTrustFileInfo{})),
		FilePath: name,
	}
	data := &windows.WinTrustData{
		Size:     uint32(unsafe.Sizeof(windows.WinTrustData{})),
		UIChoice: windows.WTD_UI_NONE,
		// No revocation check: a school computer without a connection to the
		// CRL server would fail a signature that is in fact good.
		RevocationChecks:                windows.WTD_REVOKE_NONE,
		UnionChoice:                     windows.WTD_CHOICE_FILE,
		StateAction:                     windows.WTD_STATEACTION_VERIFY,
		FileOrCatalogOrBlobOrSgnrOrCert: unsafe.Pointer(file),
	}
	verifyErr := windows.WinVerifyTrustEx(windows.InvalidHWND, &windows.WINTRUST_ACTION_GENERIC_VERIFY_V2, data)
	// The verification holds a handle in data.StateData until it is closed.
	data.StateAction = windows.WTD_STATEACTION_CLOSE
	_ = windows.WinVerifyTrustEx(windows.InvalidHWND, &windows.WINTRUST_ACTION_GENERIC_VERIFY_V2, data)

	if verifyErr == nil {
		return nil
	}
	// Windows reports a file without a signature in three ways, depending on
	// what it managed to read from it.
	for _, unsigned := range []windows.Handle{
		windows.TRUST_E_NOSIGNATURE,
		windows.TRUST_E_SUBJECT_FORM_UNKNOWN,
		windows.TRUST_E_PROVIDER_UNKNOWN,
	} {
		if errors.Is(verifyErr, windows.Errno(unsigned)) {
			return fmt.Errorf("%w: %s (%v)", ErrNotSigned, path, verifyErr)
		}
	}
	return fmt.Errorf("подпись файла %s не прошла проверку: %w", path, verifyErr)
}
