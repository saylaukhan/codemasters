//go:build !windows

package service

import "os/user"

// Name of the systemd unit. kardianos/service builds the unit file name from
// it, so `vko-agent status` and `vko-agent uninstall` find exactly the unit
// the Linux package installs — installer/linux/systemd/vko-agent.service (T-52).
const Name = "vko-agent"

// UnitUserName is the system account the Linux package creates; the unit runs
// as it instead of root («минимум прав», plan.md §4.1).
const UnitUserName = "vko-agent"

// serviceUserName is the account of the unit registered by `vko-agent install`.
// It is empty when the package has not created UnitUserName: installing the
// service by hand on a host without the package must still give a working
// unit, and that one runs as root, as it did before T-52.
func serviceUserName() string {
	if _, err := user.Lookup(UnitUserName); err != nil {
		return ""
	}
	return UnitUserName
}

// setRecoveryActions is a no-op outside Windows: systemd restarts the unit
// through Restart=on-failure in the unit file.
func setRecoveryActions(string) error { return nil }
