//go:build !windows

package service

// windowsUserName is empty outside Windows: systemd runs the unit as root
// until a dedicated user is created by the Linux package.
const windowsUserName = ""

// setRecoveryActions is a no-op outside Windows: systemd restarts the unit
// through Restart=on-failure in the unit file.
func setRecoveryActions(string) error { return nil }
